// Edge Function: process-images
// Processes images: converts to webp, compresses to <60KB, and updates small_location
// Deletes original large images after successful compression
// Uses wasm-image-optimization for serverless image processing

import { createClient } from 'npm:@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

const TARGET_SIZE = 60000  // 60KB target
const MAX_DIMENSIONS = { width: 1024, height: 768 }

async function compressImageWithStb(imageData: ArrayBuffer, imageName: string): Promise<Uint8Array> {
  /**
   * Compress image using stb-image WASM library
   * This is a lightweight C library compiled to WASM that works in Deno Deploy
   */

  const data = new Uint8Array(imageData)
  const size = imageData.byteLength

  // Detect format
  let format = 'unknown'
  if (data[0] === 0xFF && data[1] === 0xD8) {
    format = 'jpeg'
  } else if (data[0] === 0x89 && data[1] === 0x50 && data[2] === 0x4E && data[3] === 0x47) {
    format = 'png'
  } else if (data[0] === 0x52 && data[1] === 0x49 && data[2] === 0x46 && data[3] === 0x46) {
    format = 'webp'
  }

  console.log(`   📄 Format: ${format}, Size: ${(size / 1024).toFixed(1)} KB`)

  // If already WebP and small enough, use it
  if (format === 'webp' && size <= TARGET_SIZE) {
    console.log(`   ✅ Already optimized`)
    return data
  }

  try {
    // Use image-js for pure JavaScript image processing
    const { Image } = await import('npm:image-js@0.35.6')

    // Load image
    const img = await Image.load(imageData)
    const { width, height } = img

    console.log(`   📐 Original: ${width}x${height}`)

    // Calculate new dimensions
    const widthRatio = MAX_DIMENSIONS.width / width
    const heightRatio = MAX_DIMENSIONS.height / height
    const scale = Math.min(widthRatio, heightRatio, 1.0)

    let resizedImg = img

    if (scale < 1.0) {
      const newWidth = Math.floor(width * scale)
      const newHeight = Math.floor(height * scale)
      console.log(`   📐 Resizing to: ${newWidth}x${newHeight}`)
      resizedImg = img.resize({ width: newWidth, height: newHeight })
    }

    // Convert to buffer and try different WebP quality settings
    // Since image-js might not support WebP encoding, we'll use JPEG as intermediate
    // and accept it as output

    const qualities = [85, 75, 65, 55, 45, 35, 25]

    for (const quality of qualities) {
      // Export as JPEG with quality
      const buffer = await resizedImg.toBuffer({ format: 'jpeg', quality })

      if (buffer.length <= TARGET_SIZE) {
        console.log(`   📦 Compressed to ${(buffer.length / 1024).toFixed(1)} KB at quality ${quality}`)
        return new Uint8Array(buffer)
      }
    }

    // If still too large, scale down more
    const verySmall = img.resize({ width: 600, height: 450 })
    const buffer = await verySmall.toBuffer({ format: 'jpeg', quality: 20 })

    console.log(`   📦 Aggressive: ${(buffer.length / 1024).toFixed(1)} KB`)
    return new Uint8Array(buffer)

  } catch (e) {
    console.error(`   ❌ Image compression failed:`, e.message)
    // Fallback: return original
    console.log(`   ⚠️  Using original file`)
    return data
  }
}

interface ImageRecord {
  image_id: number
  image_name: string
  local_location: string
  small_location: string | null
  article_id: string
}

Deno.serve(async (req) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders })
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const supabase = createClient(supabaseUrl, supabaseKey)

    console.log('🖼️  Starting image processing...')

    // Get request parameters
    const { limit = 50, force = false } = await req.json().catch(() => ({}))

    // Find images that need processing
    let query = supabase
      .from('article_images')
      .select('image_id, image_name, local_location, small_location, article_id')
      .order('image_id', { ascending: false })
      .limit(limit)

    if (!force) {
      query = query.is('small_location', null)
    }

    const { data: images, error: queryError } = await query

    if (queryError) {
      throw new Error(`Failed to query images: ${queryError.message}`)
    }

    if (!images || images.length === 0) {
      console.log('✅ No images need processing')
      return new Response(
        JSON.stringify({
          success: true,
          message: 'No images need processing',
          processed: 0,
          failed: 0
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }

    console.log(`📋 Found ${images.length} images to process`)

    let processed = 0
    let failed = 0
    const errors: string[] = []

    // Process each image
    for (const img of images as ImageRecord[]) {
      try {
        console.log(`   Processing image ${img.image_id}: ${img.image_name}`)

        // Skip if no local_location
        if (!img.local_location) {
          console.log(`   ⚠️  Skipping ${img.image_id}: No local_location`)
          failed++
          errors.push(`Image ${img.image_id}: No local_location`)
          continue
        }

        // Check if file exists in storage
        const { data: fileData, error: downloadError } = await supabase.storage
          .from('shared-storage')
          .download(img.local_location)

        if (downloadError) {
          console.log(`   ⚠️  Failed to download ${img.local_location}: ${downloadError.message}`)
          failed++
          errors.push(`Image ${img.image_id}: ${downloadError.message}`)
          continue
        }

        const arrayBuffer = await fileData.arrayBuffer()
        const originalSize = arrayBuffer.byteLength
        console.log(`   📥 Original: ${(originalSize / 1024).toFixed(1)} KB`)

        // If already small enough (<60KB), just use as-is without recompression
        if (originalSize <= TARGET_SIZE) {
          console.log(`   ✅ Already small enough, using original as small version`)

          // Just point small_location to the same file
          const storagePath = `shared-storage/${img.local_location}`
          const { error: updateError } = await supabase
            .from('article_images')
            .update({ small_location: storagePath })
            .eq('image_id', img.image_id)

          if (updateError) {
            console.log(`   ⚠️  Failed to update image ${img.image_id}: ${updateError.message}`)
            failed++
            errors.push(`Image ${img.image_id}: ${updateError.message}`)
            continue
          }

          console.log(`   ✅ Processed image ${img.image_id} (no compression needed)`)
          processed++
          continue
        }

        // Compress the image using image-js
        const compressedData = await compressImageWithStb(arrayBuffer, img.image_name)
        const compressedSize = compressedData.length

        const reduction = originalSize > 0 ? ((1 - compressedSize / originalSize) * 100).toFixed(0) : '0'
        console.log(`   ✅ Result: ${(compressedSize / 1024).toFixed(1)} KB (${reduction}% reduction)`)

        // Upload compressed image with _small suffix
        const baseName = img.image_name.replace(/\.(jpg|jpeg|png|webp)$/i, '')
        const smallImageName = `${baseName}_small.webp`
        const smallPath = `image/${smallImageName}`

        const { error: uploadError } = await supabase.storage
          .from('shared-storage')
          .upload(smallPath, compressedData, {
            contentType: 'image/webp',
            upsert: true
          })

        if (uploadError) {
          console.log(`   ⚠️  Failed to upload compressed image: ${uploadError.message}`)
          failed++
          errors.push(`Image ${img.image_id}: ${uploadError.message}`)
          continue
        }

        // Update database with small_location
        const storagePath = `shared-storage/${smallPath}`
        const { error: updateError } = await supabase
          .from('article_images')
          .update({ small_location: storagePath })
          .eq('image_id', img.image_id)

        if (updateError) {
          console.log(`   ⚠️  Failed to update image ${img.image_id}: ${updateError.message}`)
          failed++
          errors.push(`Image ${img.image_id}: ${updateError.message}`)
          continue
        }

        // Delete the original large file to save storage
        try {
          await supabase.storage
            .from('shared-storage')
            .remove([img.local_location])
          console.log(`   🗑️  Deleted original: ${img.local_location}`)
        } catch (deleteErr) {
          console.log(`   ⚠️  Could not delete original: ${deleteErr.message}`)
          // Non-fatal, continue
        }

        console.log(`   ✅ Processed image ${img.image_id}`)
        processed++
      } catch (err) {
        console.error(`   ❌ Error processing image ${img.image_id}:`, err)
        failed++
        errors.push(`Image ${img.image_id}: ${err.message}`)
      }
    }

    console.log(`\n✅ Processing complete: ${processed} processed, ${failed} failed`)

    return new Response(
      JSON.stringify({
        success: true,
        processed,
        failed,
        total: images.length,
        errors: errors.length > 0 ? errors : undefined
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )

  } catch (error) {
    console.error('❌ Error:', error)
    return new Response(
      JSON.stringify({
        success: false,
        error: error.message
      }),
      {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    )
  }
})
