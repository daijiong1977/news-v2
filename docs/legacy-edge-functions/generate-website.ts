// Edge Function: generate-website
// Generates complete website bundle with payloads and images

import { createClient } from 'npm:@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface MainPayload {
  articles: Array<{
    id: number
    title: string
    image_url: string
    created_at: string
  }>
}

interface ArticlePayload {
  id: number
  title: string
  image_url: string
  content: string
  questions?: Array<{
    question: string
    options: string[]
    correct: number
  }>
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const supabase = createClient(supabaseUrl, supabaseKey)

    console.log('🚀 Starting website generation...')

    // Get today's date
    const today = new Date().toISOString().split('T')[0]

    // 1. Fetch articles
    console.log('📰 Fetching articles...')
    const { data: articles, error: articlesError } = await supabase
      .from('articles')
      .select('id, title, article_url, publish_date, category_id')
      .gte('created_at', today)
      .eq('deepseek_processed', true)
      .order('created_at', { ascending: false })

    if (articlesError) throw articlesError
    console.log(`   Found ${articles?.length || 0} articles`)

    if (!articles || articles.length === 0) {
      return new Response(
        JSON.stringify({ error: 'No articles found for today' }),
        { status: 404, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }

    // Get article IDs
    const articleIds = articles.map(a => a.id)

    // 2. Fetch images for these articles
    const { data: images } = await supabase
      .from('article_images')
      .select('article_id, image_name')
      .in('article_id', articleIds)

    // 3. Fetch responses for these articles
    const { data: responses } = await supabase
      .from('response')
      .select('article_id, response_data')
      .in('article_id', articleIds)

    // 4. Fetch categories
    const { data: categories } = await supabase
      .from('categories')
      .select('category_id, category_name')

    // Create lookup maps
    const imageMap = new Map(images?.map(img => [img.article_id, img.image_name]))
    const responseMap = new Map(responses?.map(r => [r.article_id, r.response_data]))
    const categoryMap = new Map(categories?.map(c => [c.category_id, c.category_name]))

    // 2. Generate main payloads (12 files: news/science/fun × easy/middle/high/cn)
    console.log('📦 Generating main payloads...')
    const main_payloads: { [key: string]: MainPayload } = {}

    const categoryNames = ['news', 'science', 'fun']
    const levels = ['easy', 'middle', 'high', 'cn']

    for (const categoryName of categoryNames) {
      for (const level of levels) {
        const key = `articles_${categoryName}_${level}`
        main_payloads[key] = { articles: [] }

        // Filter articles by category
        const categoryArticles = articles.filter(a => {
          const catName = categoryMap.get(a.category_id)
          return catName?.toLowerCase() === categoryName
        })

        for (const article of categoryArticles) {
          const responseData = responseMap.get(article.id)
          const levelData = responseData?.article_analysis?.levels?.[level]

          if (levelData) {
            const imageName = imageMap.get(article.id)
            main_payloads[key].articles.push({
              id: article.id,
              title: levelData.title || article.title,
              image_url: imageName ? `/article_images/${imageName}` : '',
              created_at: article.publish_date || new Date().toISOString()
            })
          }
        }
      }
    }

    console.log(`   Generated ${Object.keys(main_payloads).length} main payloads`)

    // 3. Generate article payloads (15 articles × 3 levels)
    console.log('📄 Generating article payloads...')
    const article_payloads: { [key: string]: { [level: string]: ArticlePayload } } = {}

    for (const article of articles) {
      const responseData = responseMap.get(article.id)
      if (!responseData?.article_analysis?.levels) continue

      const levels = responseData.article_analysis.levels
      const articleDir = `payload_${article.id}`
      article_payloads[articleDir] = {}

      const imageName = imageMap.get(article.id)

      for (const [level, levelData] of Object.entries(levels)) {
        if (level === 'cn') continue // Skip CN for article pages

        article_payloads[articleDir][level] = {
          id: article.id,
          title: levelData.title || article.title,
          image_url: imageName ? `/article_images/${imageName}` : '',
          content: levelData.content || '',
          questions: levelData.questions || []
        }
      }
    }

    console.log(`   Generated ${Object.keys(article_payloads).length} article payloads`)

    // 4. Get today's images
    console.log('🖼️  Fetching images...')
    const { data: images, error: imagesError } = await supabase
      .from('article_images')
      .select('image_name, storage_path')
      .gte('created_at', today)

    if (imagesError) throw imagesError
    console.log(`   Found ${images?.length || 0} images`)

    // 5. Download images from storage
    console.log('📥 Downloading images...')
    const image_files: { [key: string]: string } = {} // filename -> base64

    for (const img of images || []) {
      const { data: imageData, error: downloadError } = await supabase
        .storage
        .from('shared-storage')
        .download(img.storage_path.replace('shared-storage/', ''))

      if (downloadError) {
        console.error(`   ⚠️  Failed to download ${img.image_name}:`, downloadError)
        continue
      }

      // Convert to base64
      const arrayBuffer = await imageData.arrayBuffer()
      const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)))
      image_files[img.image_name] = base64
      console.log(`   ✓ ${img.image_name}`)
    }

    // 6. Load static files from local directory
    console.log('📋 Loading static files...')
    const static_files: { [key: string]: string } = {}

    // Note: These files should be in the Edge Function directory
    // For now, we'll return placeholders and handle static files separately

    // 7. Return complete bundle
    const bundle = {
      generated_at: new Date().toISOString(),
      main_payloads,
      article_payloads,
      image_files,
      static_files, // Empty for now, will be handled by git
      stats: {
        main_payloads: Object.keys(main_payloads).length,
        article_payloads: Object.keys(article_payloads).length,
        images: Object.keys(image_files).length,
        total_articles: articles?.length || 0
      }
    }

    console.log('✅ Website bundle generated successfully')
    console.log(`   - Main payloads: ${bundle.stats.main_payloads}`)
    console.log(`   - Article payloads: ${bundle.stats.article_payloads}`)
    console.log(`   - Images: ${bundle.stats.images}`)

    return new Response(
      JSON.stringify(bundle),
      {
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json'
        }
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
