/**
 * Payload Generator Edge Function
 *
 * Replicates Python mainpayload_generate.py + batch_generate_json_payloads.py logic
 *
 * Generates:
 * - 12 main page payloads: articles_{category}_{level}.json (3 categories × 4 levels)
 * - 3 files per article: payload_{article_id}/{level}.json (easy/middle/high)
 *
 * Returns: JSON bundle ready for Vercel upload + archive to Supabase Storage
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface Article {
  id: string
  title: string
  description: string
  source: string
  pub_date: string
  crawled_at: string
  category_id: number
  category_name?: string
}

interface ArticleWithImage extends Article {
  image_url: string | null
}

interface PayloadArticle {
  id: string
  title: string
  summary: string
  source: string
  time_ago: string
  image_url: string
  category: string
}

interface LevelContent {
  title: string
  summary: string
  keywords?: string[]
  questions?: string[]
  perspectives?: string[]
  background?: string
}

interface DeepSeekResponse {
  article_analysis: {
    levels: {
      easy: LevelContent
      middle: LevelContent
      high: LevelContent
      zh: LevelContent
    }
  }
}

interface PayloadBundle {
  main_payloads: Record<string, { articles: PayloadArticle[] }>
  article_payloads: Record<string, Record<string, LevelContent & { image_url: string }>>
  metadata: {
    generated_at: string
    total_articles: number
    categories: string[]
  }
}

const CATEGORIES = ['News', 'Science', 'Fun']
const LEVELS = ['easy', 'middle', 'high', 'cn']
const ARTICLE_LEVELS = ['easy', 'middle', 'high']

/**
 * Get articles from database grouped by category
 *
 * Selection criteria:
 * - 6 articles per category
 * - Max 4 articles from same source
 * - Most recent pub_date first
 * - Only processed articles (deepseek_processed = true)
 */
async function getArticlesByCategory(
  supabase: any,
  categoryName: string,
  limit: number = 6,
  maxPerSource: number = 4
): Promise<ArticleWithImage[]> {
  try {
    // Get category ID
    const { data: categories } = await supabase
      .from('categories')
      .select('category_id')
      .eq('category_name', categoryName)
      .single()

    if (!categories) {
      console.error(`Category ${categoryName} not found`)
      return []
    }

    // Get today's date (UTC-5 Eastern Time) to prioritize today's articles
    const now = new Date()
    const easternTime = new Date(now.getTime() - (5 * 60 * 60 * 1000))
    const today = easternTime.toISOString().split('T')[0]

    console.log(`📅 Today's date (Eastern Time, UTC-5): ${today}`)

    // Get all processed articles in this category, sorted by pub_date DESC (nulls last)
    const { data: articles, error } = await supabase
      .from('articles')
      .select(`
        id,
        title,
        description,
        source,
        pub_date,
        crawled_at,
        category_id
      `)
      .eq('deepseek_processed', true)
      .eq('category_id', categories.category_id)
      .order('pub_date', { ascending: false, nullsFirst: false })
      .order('id', { ascending: false })  // Secondary sort by ID for consistency

    if (error) throw error
    if (!articles || articles.length === 0) {
      console.log(`⚠️  No processed articles found for ${categoryName}`)
      return []
    }

    // Separate today's articles from older articles
    const todayArticles = articles.filter(a => a.pub_date && a.pub_date.startsWith(today))
    const olderArticles = articles.filter(a => !a.pub_date || !a.pub_date.startsWith(today))

    console.log(`📊 ${categoryName}: Found ${articles.length} processed articles (${todayArticles.length} from today, ${olderArticles.length} older)`)

    if (todayArticles.length > 0) {
      console.log(`   Today's articles: ${todayArticles.slice(0, 3).map(a => `${a.id.slice(0, 10)} (${a.source})`).join(', ')}`)
    }

    // Prioritize today's articles, then older ones
    const prioritizedArticles = [...todayArticles, ...olderArticles]

    // Apply max-per-source limit
    const selectedArticles: Article[] = []
    const sourceCount: Record<string, number> = {}

    for (const article of prioritizedArticles) {
      const source = article.source || 'Unknown'
      sourceCount[source] = sourceCount[source] || 0

      if (sourceCount[source] < maxPerSource) {
        selectedArticles.push(article)
        sourceCount[source]++
        const isToday = article.pub_date && article.pub_date.startsWith(today)
        console.log(`   ${isToday ? '✓' : '○'} Selected: ${article.id.slice(0, 10)} from ${source} (${sourceCount[source]}/${maxPerSource}) - ${article.pub_date}${isToday ? ' [TODAY]' : ''}`)

        if (selectedArticles.length >= limit) break
      } else {
        console.log(`   ✗ Skipped: ${article.id.slice(0, 10)} from ${source} (limit ${maxPerSource} reached)`)
      }
    }

    console.log(`   Final selection: ${selectedArticles.length} articles (${selectedArticles.filter(a => a.pub_date?.startsWith(today)).length} from today)`)

    // Get images for selected articles
    const articleIds = selectedArticles.map(a => a.id)
    const { data: images } = await supabase
      .from('article_images')
      .select('article_id, image_name')
      .in('article_id', articleIds)

    const imageMap: Record<string, string> = {}
    if (images) {
      images.forEach((img: any) => {
        // Generate Vercel path for images
        imageMap[img.article_id] = `/article_images/${img.image_name}`
      })
    }

    // Combine articles with images
    const articlesWithImages = selectedArticles.map(article => ({
      ...article,
      image_url: imageMap[article.id] || null,
      category_name: categoryName
    }))

    return articlesWithImages
  } catch (error) {
    console.error(`Error loading articles for ${categoryName}:`, error)
    return []
  }
}

/**
 * Load DeepSeek JSON response from Supabase Storage
 */
async function loadDeepSeekResponse(
  supabase: any,
  articleId: string
): Promise<DeepSeekResponse | null> {
  try {
    const { data, error } = await supabase.storage
      .from('shared-storage')
      .download(`json/${articleId}.json`)

    if (error) {
      console.error(`Error loading response for ${articleId}:`, error)
      return null
    }

    const text = await data.text()
    let parsed = JSON.parse(text)

    console.log(`📥 Loading ${articleId}: has raw_response=${!!parsed.raw_response}, has meta=${!!parsed.meta}, has article_analysis=${!!parsed.article_analysis}`)

    // Handle case where response has raw_response as a stringified JSON
    if (parsed.raw_response && typeof parsed.raw_response === 'string') {
      console.log(`🔓 Unwrapping raw_response string for ${articleId}`)
      try {
        parsed = JSON.parse(parsed.raw_response)
        console.log(`   After unwrap: has meta=${!!parsed.meta}, has article_analysis=${!!parsed.article_analysis}`)
      } catch (parseError) {
        console.error(`❌ Failed to parse raw_response for ${articleId}:`, parseError)
        console.error(`   First 200 chars: ${parsed.raw_response.slice(0, 200)}`)
        return null  // Return null so we fall back to original article description
      }
    }

    // Handle case where response has a 'meta' wrapper
    // DeepSeek may return: { meta: {...}, article_analysis: {...} }
    // We only need the article_analysis part
    if (parsed.meta && parsed.article_analysis) {
      console.log(`🎯 Stripping meta wrapper for ${articleId}`)
      const result = { article_analysis: parsed.article_analysis }
      console.log(`   Result has levels: ${!!result.article_analysis?.levels}`)
      return result
    }

    console.log(`✓ Using parsed structure directly for ${articleId}`)
    return parsed
  } catch (error) {
    console.error(`Error parsing response for ${articleId}:`, error)
    return null
  }
}

/**
 * Calculate time ago from pub_date
 */
function getTimeAgo(pubDate: string): string {
  try {
    const dt = new Date(pubDate)
    const now = new Date()
    const hoursAgo = Math.floor((now.getTime() - dt.getTime()) / (1000 * 60 * 60))

    if (hoursAgo <= 0) return 'Just now'
    if (hoursAgo === 1) return '1 hour ago'
    if (hoursAgo < 24) return `${hoursAgo} hours ago`

    const daysAgo = Math.floor(hoursAgo / 24)
    if (daysAgo === 1) return '1 day ago'
    return `${daysAgo} days ago`
  } catch {
    return 'Recently'
  }
}

/**
 * Generate article data for a specific level
 */
function generateArticleData(
  article: ArticleWithImage,
  response: DeepSeekResponse | null,
  level: string
): PayloadArticle {
  const levelMap: Record<string, string> = {
    'easy': 'easy',
    'middle': 'middle',
    'high': 'high',
    'cn': 'zh'
  }

  const responseLevel = levelMap[level] || level
  let title = article.title
  let summary = article.description

  // Extract level-specific content from DeepSeek response
  if (response?.article_analysis?.levels) {
    const levelContent = response.article_analysis.levels[responseLevel as keyof typeof response.article_analysis.levels]
    if (levelContent) {
      console.log(`  📝 ${article.id.slice(0,10)} [${level}]: Using DeepSeek title/summary`)
      title = levelContent.title || title
      summary = levelContent.summary || summary
    } else {
      console.log(`  ⚠️  ${article.id.slice(0,10)} [${level}]: No content for level '${responseLevel}'`)
    }
  } else {
    console.log(`  ⚠️  ${article.id.slice(0,10)} [${level}]: No levels found in response`)
  }

  return {
    id: article.id,
    title,
    summary,
    source: article.source || 'News Source',
    time_ago: getTimeAgo(article.pub_date),
    image_url: article.image_url || '',
    category: article.category_name || ''
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
    // Initialize Supabase client with service role (for storage access)
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    console.log('Starting payload generation...')

    // 1. Generate main page payloads (12 files: 3 categories × 4 levels)
    const mainPayloads: Record<string, { articles: PayloadArticle[] }> = {}
    const allArticles: ArticleWithImage[] = []

    for (const categoryName of CATEGORIES) {
      console.log(`\nProcessing category: ${categoryName}`)
      const articles = await getArticlesByCategory(supabase, categoryName, 6, 4)

      console.log(`Found ${articles.length} articles for ${categoryName}`)
      allArticles.push(...articles)

      // Generate payloads for each level
      for (const level of LEVELS) {
        const payloadArticles: PayloadArticle[] = []

        for (const article of articles) {
          // Load DeepSeek response
          const response = await loadDeepSeekResponse(supabase, article.id)
          const articleData = generateArticleData(article, response, level)
          payloadArticles.push(articleData)
        }

        const key = `articles_${categoryName.toLowerCase()}_${level}`
        mainPayloads[key] = { articles: payloadArticles }
        console.log(`Generated ${key}: ${payloadArticles.length} articles`)
      }
    }

    // 2. Generate article detail page payloads (3 files per article)
    const articlePayloads: Record<string, Record<string, LevelContent & { image_url: string }>> = {}

    for (const article of allArticles) {
      const response = await loadDeepSeekResponse(supabase, article.id)

      if (!response || !response.article_analysis || !response.article_analysis.levels) {
        console.warn(`No valid response for article ${article.id}, skipping detail payloads`)
        continue
      }

      const articleLevelPayloads: Record<string, LevelContent & { image_url: string }> = {}

      for (const level of ARTICLE_LEVELS) {
        const levelContent = response.article_analysis.levels[level as keyof typeof response.article_analysis.levels]

        if (levelContent) {
          articleLevelPayloads[level] = {
            ...levelContent,
            image_url: article.image_url || ''
          }
        }
      }

      articlePayloads[`payload_${article.id}`] = articleLevelPayloads
      console.log(`Generated detail payloads for article ${article.id}`)
    }

    // 3. Build response bundle
    const bundle: PayloadBundle = {
      main_payloads: mainPayloads,
      article_payloads: articlePayloads,
      metadata: {
        generated_at: new Date().toISOString(),
        total_articles: allArticles.length,
        categories: CATEGORIES
      }
    }

    console.log('\n✅ Payload generation complete')
    console.log(`Total articles: ${allArticles.length}`)
    console.log(`Main payloads: ${Object.keys(mainPayloads).length}`)
    console.log(`Article payloads: ${Object.keys(articlePayloads).length}`)

    return new Response(
      JSON.stringify(bundle, null, 2),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200
      }
    )
  } catch (error) {
    console.error('Error generating payloads:', error)
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 500
      }
    )
  }
})
