import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import JSZip from 'https://esm.sh/jszip@3.10.1'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const githubToken = Deno.env.get('GITHUB_TOKEN')!

    if (!githubToken) {
      throw new Error('GITHUB_TOKEN not configured')
    }

    const owner = 'daijiong1977'
    const repo = 'kidsnews'

    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    const { website_dir } = await req.json()

    if (!website_dir) {
      throw new Error('website_dir parameter is required')
    }

    console.log(`\n📦 Creating zip from: ${website_dir}`)

    // Extract date from website_dir (e.g., "website/2025-11-11" -> "2025-11-11")
    const dateMatch = website_dir.match(/(\d{4}-\d{2}-\d{2})/)
    if (!dateMatch) {
      throw new Error(`Invalid website_dir format: ${website_dir}`)
    }
    const deployDate = dateMatch[1]

    // Create zip with all files from the website directory
    const zip = new JSZip()

    // Use queue-based approach to list all files
    const queue = [website_dir]
    let fileCount = 0

    console.log('📄 Downloading files from Storage...')

    while (queue.length > 0) {
      const currentPath = queue.shift()!

      const { data, error } = await supabase.storage
        .from('shared-storage')
        .list(currentPath, { limit: 1000 })

      if (error) {
        console.warn(`⚠️  Warning listing ${currentPath}:`, error.message)
        continue
      }

      for (const item of data) {
        const fullPath = currentPath ? `${currentPath}/${item.name}` : item.name

        if (item.id) {
          // It's a file - download and add to zip
          const { data: fileData, error: downloadError } = await supabase.storage
            .from('shared-storage')
            .download(fullPath)

          if (!downloadError && fileData) {
            // Get relative path within the zip (strip "website/2025-11-11/" prefix)
            const relativePath = fullPath.replace(`${website_dir}/`, '')
            const arrayBuffer = await fileData.arrayBuffer()
            zip.file(relativePath, arrayBuffer)
            fileCount++
          }
        } else {
          // It's a directory - add to queue
          queue.push(fullPath)
        }
      }
    }

    console.log(`   ✓ Downloaded ${fileCount} files`)

    // Generate zip in memory
    console.log('🗜️  Generating zip...')
    const zipBlob = await zip.generateAsync({ type: 'uint8array' })
    const zipSizeMB = (zipBlob.length / 1024 / 1024).toFixed(2)
    console.log(`   ✓ Zip created (${zipSizeMB} MB)`)

    // Push zip to GitHub using Git Data API
    console.log('\n📤 Pushing zip to GitHub...')

    const zipFileName = `website-${deployDate}.zip`

    // Get current commit SHA
    const refResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/refs/heads/main`,
      {
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/vnd.github.v3+json',
          'User-Agent': 'Supabase-Edge-Function'
        }
      }
    )

    if (!refResponse.ok) {
      throw new Error(`Failed to get ref: ${refResponse.status} ${await refResponse.text()}`)
    }

    const refData = await refResponse.json()
    const currentCommitSha = refData.object.sha

    // Convert zip to base64 properly for large files
    console.log('🔄 Converting to base64...')

    // Use TextDecoder approach for proper base64 encoding
    const encoder = new TextEncoder()
    const decoder = new TextDecoder('latin1')

    // Convert Uint8Array to binary string, then to base64
    const chunkSize = 32768  // Larger chunks for efficiency
    let binaryString = ''
    for (let i = 0; i < zipBlob.length; i += chunkSize) {
      const chunk = zipBlob.slice(i, Math.min(i + chunkSize, zipBlob.length))
      // Convert each byte to a character
      for (let j = 0; j < chunk.length; j++) {
        binaryString += String.fromCharCode(chunk[j])
      }
    }

    const base64Content = btoa(binaryString)
    console.log(`   ✓ Conversion complete (${base64Content.length} chars, ${(base64Content.length / 1024 / 1024).toFixed(2)} MB encoded)`)

    // Create blob for zip file
    const blobResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/blobs`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
          'User-Agent': 'Supabase-Edge-Function'
        },
        body: JSON.stringify({
          content: base64Content,
          encoding: 'base64'
        })
      }
    )

    if (!blobResponse.ok) {
      throw new Error(`Failed to create blob: ${blobResponse.status} ${await blobResponse.text()}`)
    }

    const blobData = await blobResponse.json()
    const blobSha = blobData.sha

    // Get current commit details
    const commitResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/commits/${currentCommitSha}`,
      {
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/vnd.github.v3+json',
          'User-Agent': 'Supabase-Edge-Function'
        }
      }
    )

    if (!commitResponse.ok) {
      throw new Error(`Failed to get commit: ${commitResponse.status}`)
    }

    const commitData = await commitResponse.json()
    const baseTreeSha = commitData.tree.sha

    // Create new tree with the dated zip file
    const treeResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/trees`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
          'User-Agent': 'Supabase-Edge-Function'
        },
        body: JSON.stringify({
          base_tree: baseTreeSha,
          tree: [
            {
              path: zipFileName,  // website-2025-11-12.zip
              mode: '100644',
              type: 'blob',
              sha: blobSha
            }
          ]
        })
      }
    )

    if (!treeResponse.ok) {
      throw new Error(`Failed to create tree: ${treeResponse.status} ${await treeResponse.text()}`)
    }

    const treeData = await treeResponse.json()
    const treeSha = treeData.sha

    // Create new commit
    const newCommitResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/commits`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
          'User-Agent': 'Supabase-Edge-Function'
        },
        body: JSON.stringify({
          message: `Deploy website ${deployDate}`,
          tree: treeSha,
          parents: [currentCommitSha]
        })
      }
    )

    if (!newCommitResponse.ok) {
      throw new Error(`Failed to create commit: ${newCommitResponse.status} ${await newCommitResponse.text()}`)
    }

    const newCommitData = await newCommitResponse.json()
    const newCommitSha = newCommitData.sha

    // Update reference
    const updateRefResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/refs/heads/main`,
      {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
          'User-Agent': 'Supabase-Edge-Function'
        },
        body: JSON.stringify({
          sha: newCommitSha,
          force: false
        })
      }
    )

    if (!updateRefResponse.ok) {
      throw new Error(`Failed to update ref: ${updateRefResponse.status} ${await updateRefResponse.text()}`)
    }

    console.log(`   ✓ Pushed to GitHub: https://github.com/${owner}/${repo}/blob/main/${zipFileName}`)

    return new Response(
      JSON.stringify({
        success: true,
        zip_file: zipFileName,
        zip_size_mb: zipSizeMB,
        files_count: fileCount,
        github_url: `https://github.com/${owner}/${repo}/blob/main/${zipFileName}`,
        website_dir,
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    )

  } catch (error) {
    console.error('❌ Error:', error)
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    )
  }
})
