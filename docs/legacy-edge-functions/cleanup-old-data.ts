/**
 * Cleanup Old Data Edge Function
 *
 * Deletes articles, JSON files, and payloads older than 31 days to save space
 *
 * Process:
 * 1. Find articles where crawled_at < (now - 31 days)
 * 2. Delete from articles table (cascade to article_images, response, etc.)
 * 3. Delete JSON files from shared-storage/json/
 * 4. Delete archived payloads from storage (if implemented)
 *
 * Can be triggered manually or via pg_cron schedule
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface CleanupResult {
  articles_deleted: number
  json_files_deleted: number
  storage_errors: string[]
  deleted_article_ids: string[]
  summary: string
}

/**
 * Get articles older than retention days
 */
async function getOldArticles(
  supabase: any,
  retentionDays: number = 31
): Promise<string[]> {
  try {
    const cutoffDate = new Date()
    cutoffDate.setDate(cutoffDate.getDate() - retentionDays)
    const cutoffIso = cutoffDate.toISOString()

    console.log(`Finding articles older than ${cutoffIso} (${retentionDays} days)`)

    const { data, error } = await supabase
      .from('articles')
      .select('id, crawled_at, title')
      .lt('crawled_at', cutoffIso)
      .order('crawled_at', { ascending: true })

    if (error) throw error

    if (!data || data.length === 0) {
      console.log('No old articles found')
      return []
    }

    console.log(`Found ${data.length} articles to delete`)
    data.forEach((article: any) => {
      console.log(`  - ${article.id}: ${article.title?.substring(0, 60)} (${article.crawled_at})`)
    })

    return data.map((a: any) => a.id)
  } catch (error) {
    console.error('Error finding old articles:', error)
    throw error
  }
}

/**
 * Delete JSON files from storage
 */
async function deleteJsonFiles(
  supabase: any,
  articleIds: string[]
): Promise<{ deleted: number; errors: string[] }> {
  const errors: string[] = []
  let deleted = 0

  for (const articleId of articleIds) {
    try {
      const { error } = await supabase.storage
        .from('shared-storage')
        .remove([`json/${articleId}.json`])

      if (error) {
        console.error(`Error deleting JSON for ${articleId}:`, error)
        errors.push(`${articleId}: ${error.message}`)
      } else {
        deleted++
        console.log(`Deleted JSON file for ${articleId}`)
      }
    } catch (error) {
      console.error(`Exception deleting JSON for ${articleId}:`, error)
      errors.push(`${articleId}: ${error.message}`)
    }
  }

  return { deleted, errors }
}

/**
 * Delete article images from storage
 */
async function deleteArticleImages(
  supabase: any,
  articleIds: string[]
): Promise<{ deleted: number; errors: string[] }> {
  const errors: string[] = []
  let deleted = 0

  // Get image locations from database before deletion
  const { data: images } = await supabase
    .from('article_images')
    .select('article_id, small_location, original_location')
    .in('article_id', articleIds)

  if (images && images.length > 0) {
    const filesToDelete: string[] = []

    images.forEach((img: any) => {
      // Extract filename from path
      if (img.small_location) {
        const smallFile = img.small_location.split('/').pop()
        if (smallFile) filesToDelete.push(`image/${smallFile}`)
      }
      if (img.original_location) {
        const originalFile = img.original_location.split('/').pop()
        if (originalFile) filesToDelete.push(`image/${originalFile}`)
      }
    })

    if (filesToDelete.length > 0) {
      try {
        const { error } = await supabase.storage
          .from('shared-storage')
          .remove(filesToDelete)

        if (error) {
          console.error('Error deleting images:', error)
          errors.push(`Images: ${error.message}`)
        } else {
          deleted = filesToDelete.length
          console.log(`Deleted ${deleted} image files`)
        }
      } catch (error) {
        console.error('Exception deleting images:', error)
        errors.push(`Images: ${error.message}`)
      }
    }
  }

  return { deleted, errors }
}

/**
 * Delete articles from database (cascade to related tables)
 */
async function deleteArticles(
  supabase: any,
  articleIds: string[]
): Promise<number> {
  try {
    const { error, count } = await supabase
      .from('articles')
      .delete({ count: 'exact' })
      .in('id', articleIds)

    if (error) throw error

    console.log(`Deleted ${count || articleIds.length} articles from database`)
    return count || articleIds.length
  } catch (error) {
    console.error('Error deleting articles:', error)
    throw error
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
    // Parse request body (optional: allow custom retention days)
    let retentionDays = 31
    try {
      const body = await req.json()
      if (body.retention_days && typeof body.retention_days === 'number') {
        retentionDays = body.retention_days
      }
    } catch {
      // Use default if no body or invalid JSON
    }

    // Initialize Supabase client with service role
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    console.log(`\n🧹 Starting cleanup (retention: ${retentionDays} days)`)

    // 1. Find old articles
    const oldArticleIds = await getOldArticles(supabase, retentionDays)

    if (oldArticleIds.length === 0) {
      const result: CleanupResult = {
        articles_deleted: 0,
        json_files_deleted: 0,
        storage_errors: [],
        deleted_article_ids: [],
        summary: `No articles older than ${retentionDays} days found. Nothing to clean up.`
      }

      return new Response(
        JSON.stringify(result, null, 2),
        {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 200
        }
      )
    }

    const storageErrors: string[] = []

    // 2. Delete JSON files from storage
    console.log('\n📄 Deleting JSON files...')
    const jsonResult = await deleteJsonFiles(supabase, oldArticleIds)
    storageErrors.push(...jsonResult.errors)

    // 3. Delete image files from storage
    console.log('\n🖼️  Deleting image files...')
    const imageResult = await deleteArticleImages(supabase, oldArticleIds)
    storageErrors.push(...imageResult.errors)

    // 4. Delete articles from database (this cascades to related tables)
    console.log('\n🗑️  Deleting articles from database...')
    const articlesDeleted = await deleteArticles(supabase, oldArticleIds)

    // Build result
    const result: CleanupResult = {
      articles_deleted: articlesDeleted,
      json_files_deleted: jsonResult.deleted,
      storage_errors: storageErrors,
      deleted_article_ids: oldArticleIds,
      summary: `Cleaned up ${articlesDeleted} articles older than ${retentionDays} days. ` +
               `Deleted ${jsonResult.deleted} JSON files, ${imageResult.deleted} image files. ` +
               `${storageErrors.length} storage errors encountered.`
    }

    console.log('\n✅ Cleanup complete')
    console.log(`Articles: ${articlesDeleted}`)
    console.log(`JSON files: ${jsonResult.deleted}`)
    console.log(`Images: ${imageResult.deleted}`)
    console.log(`Errors: ${storageErrors.length}`)

    return new Response(
      JSON.stringify(result, null, 2),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200
      }
    )
  } catch (error) {
    console.error('Error during cleanup:', error)
    return new Response(
      JSON.stringify({
        error: error.message,
        summary: 'Cleanup failed'
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 500
      }
    )
  }
})
