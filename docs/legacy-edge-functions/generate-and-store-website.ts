// Edge Function: generate-and-store-website
// Generates payloads, downloads images, stores in Supabase Storage, and creates zip

import { createClient } from 'npm:@supabase/supabase-js@2'
import JSZip from 'npm:jszip@3.10.1'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!

    if (!supabaseUrl || !supabaseKey) {
      throw new Error('Missing required environment variables: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY')
    }

    console.log(`🔑 Using Supabase URL: ${supabaseUrl}`)
    console.log(`🔑 Service key length: ${supabaseKey?.length || 0} chars`)

    const supabase = createClient(supabaseUrl, supabaseKey)

    console.log('🚀 Starting website generation and storage...')
    // Use UTC-5 (Eastern Time) for date calculation
    const now = new Date()
    const easternTime = new Date(now.getTime() - (5 * 60 * 60 * 1000))
    const today = easternTime.toISOString().split('T')[0]

    console.log(`📅 Target date: ${today} (Eastern Time, UTC-5)`)
    console.log(`   Current UTC time: ${now.toISOString()}`)
    console.log(`   Eastern Time: ${easternTime.toISOString()}`)

    // Delete existing directory if it exists
    console.log(`🗑️  Cleaning up existing files for ${today}...`)
    const websiteDir = `website/${today}`

    // Delete old directory recursively
    async function deleteDirectory(path: string) {
      const { data: items } = await supabase.storage
        .from('shared-storage')
        .list(path, { limit: 1000 })

      if (!items || items.length === 0) return

      const filesToDelete: string[] = []
      const dirsToDelete: string[] = []

      for (const item of items) {
        const fullPath = `${path}/${item.name}`
        if (item.id) {
          // It's a file
          filesToDelete.push(fullPath)
        } else {
          // It's a directory - recurse first
          dirsToDelete.push(fullPath)
        }
      }

      // Delete files first
      if (filesToDelete.length > 0) {
        await supabase.storage.from('shared-storage').remove(filesToDelete)
      }

      // Then recurse into subdirectories
      for (const dir of dirsToDelete) {
        await deleteDirectory(dir)
      }
    }

    try {
      await deleteDirectory(websiteDir)
      console.log(`   ✓ Deleted old directory: ${websiteDir}`)
    } catch (e) {
      console.log(`   ℹ️  No existing directory to clean (this is normal for first run)`)
    }

    console.log(`   ✓ Cleanup complete`)

    // 1. Call existing payload-generator to get payloads
    console.log('📦 Calling payload-generator...')

    const payloadResponse = await fetch(
      `${supabaseUrl}/functions/v1/payload-generator`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${supabaseKey}`,
          'Content-Type': 'application/json',
          'x-client-info': 'supabase-js-node'
        },
        body: '{}'
      }
    )

    if (!payloadResponse.ok) {
      const errorText = await payloadResponse.text()
      console.error('Payload generator error:', errorText)
      throw new Error(`Payload generator failed: ${errorText}`)
    }

    const payloadBundle = await payloadResponse.json()
    console.log(`   ✓ Got ${Object.keys(payloadBundle.main_payloads || {}).length} main payloads`)
    console.log(`   ✓ Got ${Object.keys(payloadBundle.article_payloads || {}).length} article payloads`)

    // 2. Identify all images referenced in the payloads
    console.log('🖼️  Resolving image references...')
    const payloadAsString = JSON.stringify(payloadBundle)
    const imageMatches = payloadAsString.match(/\/?article_images\/([A-Za-z0-9_\-\.]+\.(?:png|jpe?g|webp))/g) || []
    const imageNames: string[] = Array.from(
      new Set(
        imageMatches.map((match: string) => match.replace(/^\/?article_images\//, ''))
      )
    )

    console.log(`   🔍 Found ${imageNames.length} image references in payloads`)

    const imageLookup = new Map()

    if (imageNames.length > 0) {
      const { data: imageRecords, error: imageQueryError } = await supabase
        .from('article_images')
        .select('image_name, small_location')
        .in('image_name', imageNames)

      if (imageQueryError) {
        console.error('   ⚠️  Failed to fetch image metadata:', imageQueryError)
      } else if (imageRecords) {
        for (const record of imageRecords) {
          imageLookup.set(record.image_name, record.small_location)
        }
      }
    }

    // 3. Store everything in website directory
    console.log(`📁 Storing to ${websiteDir}/...`)

    let filesStored = 0

    // 3a. Store main payloads
    for (const [filename, content] of Object.entries(payloadBundle.main_payloads || {})) {
      const path = `${websiteDir}/payloads/${filename}.json`
      const { error } = await supabase.storage
        .from('shared-storage')
        .upload(path, JSON.stringify(content, null, 2), {
          contentType: 'application/json',
          upsert: true
        })

      if (error) {
        console.error(`   ⚠️  Failed to store ${path}:`, error)
      } else {
        filesStored++
      }
    }

    console.log(`   ✓ Stored ${Object.keys(payloadBundle.main_payloads || {}).length} main payloads`)

    // 3b. Store article payloads
    for (const [articleDir, levels] of Object.entries(payloadBundle.article_payloads || {})) {
      for (const [level, content] of Object.entries(levels)) {
        const path = `${websiteDir}/article_payloads/${articleDir}/${level}.json`
        const { error } = await supabase.storage
          .from('shared-storage')
          .upload(path, JSON.stringify(content, null, 2), {
            contentType: 'application/json',
            upsert: true
          })

        if (error) {
          console.error(`   ⚠️  Failed to store ${path}:`, error)
        } else {
          filesStored++
        }
      }
    }

    console.log(`   ✓ Stored ${Object.keys(payloadBundle.article_payloads || {}).length} article payloads`)

    // 3c. Copy ONLY small images to website directory
    let imagesCopied = 0
    const missingImages: string[] = []

    for (const imageName of imageNames) {
      const smallLocation = imageLookup.get(imageName)

      // Skip if no small_location found - we ONLY want small images
      if (!smallLocation) {
        console.warn(`   ⚠️  No small image found for ${imageName}, skipping`)
        missingImages.push(imageName)
        continue
      }

      const sourcePath = smallLocation.replace('shared-storage/', '')
      const destPath = `${websiteDir}/article_images/${imageName}`

      const { data: imageData, error: downloadError } = await supabase.storage
        .from('shared-storage')
        .download(sourcePath)

      if (downloadError) {
        console.error(`   ⚠️  Failed to download ${sourcePath}:`, downloadError)
        missingImages.push(imageName)
        continue
      }

      const { error: uploadError } = await supabase.storage
        .from('shared-storage')
        .upload(destPath, imageData, {
          contentType: 'image/webp',
          upsert: true
        })

      if (uploadError) {
        console.error(`   ⚠️  Failed to store ${destPath}:`, uploadError)
      } else {
        filesStored++
        imagesCopied++
      }
    }

    console.log(`   ✓ Copied ${imagesCopied} small images`)
    if (missingImages.length > 0) {
      console.warn(`   ⚠️  Missing ${missingImages.length} small images:`, missingImages.slice(0, 5))
    }

    // 4. Generate archive index (list all available dates)
    console.log('\n📚 Generating archive index...')
    const { data: websiteDirs, error: listError } = await supabase.storage
      .from('shared-storage')
      .list('website', { limit: 1000 })

    const archiveIndex = {
      generated_at: new Date().toISOString(),
      dates: []
    }

    if (!listError && websiteDirs) {
      // Filter for directories (date folders like 2025-11-11)
      const dateDirs = websiteDirs
        .filter(item => !item.id && /^\d{4}-\d{2}-\d{2}$/.test(item.name))
        .map(item => ({
          date: item.name,
          supabase_path: `website/${item.name}`,
          payloads_url: `https://lfknsvavhiqrsasdfyrs.supabase.co/storage/v1/object/public/shared-storage/website/${item.name}/payloads/`,
          images_url: `https://lfknsvavhiqrsasdfyrs.supabase.co/storage/v1/object/public/shared-storage/website/${item.name}/article_images/`,
          article_payloads_url: `https://lfknsvavhiqrsasdfyrs.supabase.co/storage/v1/object/public/shared-storage/website/${item.name}/article_payloads/`
        }))
        .sort((a, b) => b.date.localeCompare(a.date)) // Most recent first

      archiveIndex.dates = dateDirs
      console.log(`   ✓ Found ${dateDirs.length} archive dates`)
    }

    // Store archive index in payloads directory
    const { error: archiveError } = await supabase.storage
      .from('shared-storage')
      .upload(`${websiteDir}/payloads/archive_index.json`, JSON.stringify(archiveIndex, null, 2), {
        contentType: 'application/json',
        upsert: true
      })

    if (archiveError) {
      console.error('   ⚠️  Failed to store archive index:', archiveError)
    } else {
      console.log('   ✓ Archive index stored')
      filesStored++
    }

    // 5. Create manifest file
    const manifest = {
      generated_at: new Date().toISOString(),
      date: today,
      files: {
        main_payloads: Object.keys(payloadBundle.main_payloads || {}).length,
        article_payloads: Object.keys(payloadBundle.article_payloads || {}).length,
  images: imagesCopied,
        total: filesStored
      }
    }

    const { error: manifestError } = await supabase.storage
      .from('shared-storage')
      .upload(`${websiteDir}/manifest.json`, JSON.stringify(manifest, null, 2), {
        contentType: 'application/json',
        upsert: true
      })

    if (manifestError) {
      console.error('   ⚠️  Failed to store manifest:', manifestError)
    }

    console.log('✅ Website generation complete')
    console.log(`   Stored ${filesStored} files in ${websiteDir}`)

    return new Response(
      JSON.stringify({
        success: true,
        website_dir: websiteDir,
        files_stored: filesStored,
        manifest
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
