/**
 * JSON Cleanup Edge Function
 *
 * Validates and repairs DeepSeek JSON responses stored in Supabase Storage.
 * Handles malformed JSON, unwraps raw_response, strips meta wrappers.
 *
 * Usage:
 *   POST /cleanup-json
 *   Body: { "article_id": "836b4a1582aae819" }  // Clean specific article
 *   Body: { "all": true }                        // Clean all JSON files
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface CleanupResult {
  article_id: string
  success: boolean
  changes: string[]
  errors?: string[]
}

/**
 * Apply all known JSON cleanup patterns
 */
function cleanJsonContent(content: string): { cleaned: string; patterns: string[] } {
  let cleaned = content
  const patterns: string[] = []

  // Pattern 1: Remove extra space in keys: " "key": → "key":
  const pattern1Matches = (cleaned.match(/" "([^"]+)":/g) || []).length
  if (pattern1Matches > 0) {
    cleaned = cleaned.replace(/" "([^"]+)":/g, '"$1":')
    patterns.push(`Fixed ${pattern1Matches} malformed keys (extra space)`)
  }

  // Pattern 2: Fix closing array with quote: }"] → }]
  const pattern2Matches = (cleaned.match(/\}"\]/g) || []).length
  if (pattern2Matches > 0) {
    cleaned = cleaned.replace(/\}"\]/g, '}]')
    patterns.push(`Fixed ${pattern2Matches} malformed array closings`)
  }

  // Pattern 3: Arrays wrapped in quotes - "field": "["val"]" → "field": ["val"]
  const pattern3Matches = (cleaned.match(/"(options|correct_answer)":\s*"\[([^\]]+)\]"/g) || []).length
  if (pattern3Matches > 0) {
    cleaned = cleaned.replace(/"(options|correct_answer)":\s*"\[([^\]]+)\]"/g, '"$1": [$2]')
    patterns.push(`Fixed ${pattern3Matches} arrays wrapped in quotes`)
  }

  // Pattern 3b: Incomplete arrays - "options": "value" instead of "options": ["value"]
  // This handles cases where the array brackets are completely missing
  const pattern3bMatches = (cleaned.match(/"options":\s*"([^"]+)"(?=\s*,\s*"correct_answer")/g) || []).length
  if (pattern3bMatches > 0) {
    // Fix options field that's missing array brackets (but keep the quotes around string values)
    cleaned = cleaned.replace(/"options":\s*"([^"]+)"(?=\s*,\s*"correct_answer")/g, '"options": ["$1"]')
    patterns.push(`Fixed ${pattern3bMatches} options missing array brackets`)
  }

  // Pattern 3c: Missing opening bracket - "options": "item1", "item2"] → "options": ["item1", "item2"]
  const pattern3cMatches = (cleaned.match(/"options":\s*("(?:[^"]+)"(?:\s*,\s*"[^"]+")*)\s*\]/g) || []).length
  if (pattern3cMatches > 0) {
    cleaned = cleaned.replace(/"options":\s*("(?:[^"]+)"(?:\s*,\s*"[^"]+")*)\s*\]/g, '"options": [$1]')
    patterns.push(`Fixed ${pattern3cMatches} options missing opening bracket`)
  }

  // Pattern 4: Standalone quoted arrays on full lines
  const lines = cleaned.split('\n')
  const fixedLines: string[] = []
  let pattern4Count = 0

  for (const line of lines) {
    const match = line.match(/^(\s*"[^"]+"\s*:\s*)"\[(.*)\]"(.*)$/)
    if (match) {
      const [, prefix, arrayContent, suffix] = match
      fixedLines.push(`${prefix}[${arrayContent}]${suffix}`)
      pattern4Count++
    } else {
      fixedLines.push(line)
    }
  }

  if (pattern4Count > 0) {
    cleaned = fixedLines.join('\n')
    patterns.push(`Fixed ${pattern4Count} standalone quoted arrays`)
  }

  return { cleaned, patterns }
}

/**
 * Validate JSON structure
 */
function validateStructure(data: any): { valid: boolean; issues: string[] } {
  const issues: string[] = []

  if (!data.article_analysis) {
    issues.push('Missing article_analysis')
    return { valid: false, issues }
  }

  if (!data.article_analysis.levels) {
    issues.push('Missing levels object')
    return { valid: false, issues }
  }

  const levels = data.article_analysis.levels
  const requiredLevels = ['easy', 'middle', 'high', 'zh']

  for (const level of requiredLevels) {
    if (!levels[level]) {
      issues.push(`Missing ${level} level`)
    } else {
      if (!levels[level].title) issues.push(`${level} missing title`)
      if (!levels[level].summary) issues.push(`${level} missing summary`)
    }
  }

  return { valid: issues.length === 0, issues }
}

/**
 * Clean a single article's JSON
 */
async function cleanArticleJson(
  supabase: any,
  articleId: string
): Promise<CleanupResult> {
  const result: CleanupResult = {
    article_id: articleId,
    success: false,
    changes: [],
    errors: []
  }

  const jsonPath = `json/${articleId}.json`

  console.log(`\n${'='.repeat(80)}`)
  console.log(`Cleaning: ${articleId}`)
  console.log('='.repeat(80))

  // 1. Download from storage
  console.log('1. Downloading from storage...')
  try {
    const { data: fileData, error } = await supabase.storage
      .from('shared-storage')
      .download(jsonPath)

    if (error) throw error

    const content = await fileData.text()
    console.log(`   Downloaded ${content.length} bytes`)

    // 2. Parse original
    console.log('2. Parsing JSON...')
    let data: any
    let needsCleaning = false

    try {
      data = JSON.parse(content)
      console.log('   ✓ Valid JSON syntax')
    } catch (parseError) {
      console.log('   ⚠️  Invalid JSON, attempting cleanup...')
      result.changes.push('Applied JSON syntax cleanup')
      needsCleaning = true

      const { cleaned, patterns } = cleanJsonContent(content)
      result.changes.push(...patterns)

      try {
        data = JSON.parse(cleaned)
        console.log('   ✓ Successfully repaired JSON')
      } catch (e) {
        const errorMsg = `Still invalid after cleanup: ${e.message}`
        console.log(`   ❌ ${errorMsg}`)
        result.errors?.push(errorMsg)
        return result
      }
    }

    // 3. Unwrap raw_response
    if (data.raw_response && typeof data.raw_response === 'string') {
      console.log('3. Unwrapping raw_response...')
      result.changes.push('Unwrapped raw_response string')
      needsCleaning = true

      try {
        const inner = JSON.parse(data.raw_response)
        data = inner
        console.log('   ✓ Unwrapped successfully')
      } catch (e) {
        console.log('   Cleaning raw_response content...')
        const { cleaned, patterns } = cleanJsonContent(data.raw_response)
        result.changes.push(...patterns)

        try {
          data = JSON.parse(cleaned)
          console.log('   ✓ Cleaned and unwrapped')
        } catch (e2) {
          const errorMsg = `Failed to unwrap: ${e2.message}`
          console.log(`   ❌ ${errorMsg}`)
          result.errors?.push(errorMsg)
          return result
        }
      }
    }

    // 4. Strip meta wrapper
    if (data.meta && data.article_analysis) {
      console.log('4. Stripping meta wrapper...')
      data = { article_analysis: data.article_analysis }
      result.changes.push('Stripped meta wrapper')
      needsCleaning = true
      console.log('   ✓ Meta wrapper removed')
    }

    // 5. Validate structure
    console.log('5. Validating structure...')
    const { valid, issues } = validateStructure(data)

    if (issues.length > 0) {
      console.log(`   Found ${issues.length} issue(s):`)
      issues.forEach(issue => console.log(`   - ${issue}`))
      result.errors?.push(...issues)
    }

    if (!valid) {
      console.log('   ❌ Structure validation failed')
      return result
    }

    console.log('   ✓ Structure is valid')

    // 6. Upload cleaned version
    if (needsCleaning) {
      console.log('6. Uploading cleaned version...')
      const cleanedContent = JSON.stringify(data, null, 2)

      const { error: uploadError } = await supabase.storage
        .from('shared-storage')
        .upload(jsonPath, cleanedContent, {
          contentType: 'application/json',
          upsert: true
        })

      if (uploadError) {
        const errorMsg = `Upload failed: ${uploadError.message}`
        console.log(`   ❌ ${errorMsg}`)
        result.errors?.push(errorMsg)
        return result
      }

      console.log(`   ✓ Uploaded ${cleanedContent.length} bytes`)
      result.success = true
    } else {
      console.log('6. No changes needed')
      result.success = true
      result.changes = ['No changes needed - already clean']
    }

    return result

  } catch (error) {
    const errorMsg = `Error: ${error.message}`
    console.log(`❌ ${errorMsg}`)
    result.errors?.push(errorMsg)
    return result
  }
}

/**
 * Main handler
 */
serve(async (req) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    const { article_id, all } = await req.json()

    if (all) {
      // Clean all JSON files
      console.log('Cleaning all JSON files in storage...')

      const { data: files, error: listError } = await supabase.storage
        .from('shared-storage')
        .list('json/')

      if (listError) throw listError

      console.log(`Found ${files.length} JSON files`)

      const results: CleanupResult[] = []

      for (const file of files) {
        const id = file.name.replace('.json', '')
        const result = await cleanArticleJson(supabase, id)
        results.push(result)
      }

      const successCount = results.filter(r => r.success).length

      return new Response(
        JSON.stringify({
          success: true,
          total: results.length,
          cleaned: successCount,
          failed: results.length - successCount,
          results
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )

    } else if (article_id) {
      // Clean specific article
      const result = await cleanArticleJson(supabase, article_id)

      return new Response(
        JSON.stringify({
          success: result.success,
          ...result
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )

    } else {
      return new Response(
        JSON.stringify({ error: 'Missing article_id or all parameter' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }

  } catch (error) {
    console.error('Error:', error)
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )
  }
})
