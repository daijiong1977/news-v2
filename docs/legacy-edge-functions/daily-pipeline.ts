import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')
const SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')

async function sleep(seconds: number) {
  return new Promise(resolve => setTimeout(resolve, seconds * 1000))
}

async function callEdgeFunction(functionName: string, payload: any = {}, maxRetries = 1): Promise<any> {
  if (!SUPABASE_URL || !SERVICE_ROLE_KEY) {
    throw new Error('Supabase environment variables are not configured for daily-pipeline')
  }
  let lastError: Error | null = null

  for (let attempt = 1; attempt <= maxRetries + 1; attempt++) {
    try {
      console.log(`⏳ Starting: ${functionName} (attempt ${attempt}/${maxRetries + 1})`)
      const startTime = Date.now()

      const response = await fetch(
        `${SUPABASE_URL}/functions/v1/${functionName}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${SERVICE_ROLE_KEY}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        }
      )

      const result = await response.json()
      const duration = ((Date.now() - startTime) / 1000).toFixed(2)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${result.error || JSON.stringify(result)}`)
      }

      console.log(`✅ Completed: ${functionName} (${duration}s)`)
      return result

    } catch (error) {
      lastError = error as Error
      console.error(`❌ Attempt ${attempt} failed: ${functionName} - ${lastError.message}`)

      if (attempt <= maxRetries) {
        console.log(`⏸️  Waiting 60 seconds before retry...`)
        await sleep(60)
      }
    }
  }

  // All retries exhausted
  throw new Error(`${functionName} failed after ${maxRetries + 1} attempts: ${lastError?.message}`)
}

serve(async (req) => {
  console.log('🚀 Starting daily pipeline orchestrator...')
  const pipelineStart = Date.now()

  try {
    // Step 1: Generate website and store in Supabase Storage (for archive)
    // Note: Images are now pre-compressed by mining service, so process-images is skipped
    // Note: JSON cleanup now handled by render deepseek service - bad articles are deleted
    const step1 = await callEdgeFunction('generate-and-store-website', {})

    // Step 2: Create zip from Storage and push to GitHub (in memory, no storage)
    const step2 = await callEdgeFunction('zip-to-git', {
      website_dir: step1.website_dir
    })

    const totalDuration = ((Date.now() - pipelineStart) / 1000).toFixed(2)

    const summary = {
      success: true,
      duration: `${totalDuration}s`,
      steps: {
        generateWebsite: step1,
        pushToGithub: step2
      }
    }

    console.log(`🎉 Pipeline completed successfully in ${totalDuration}s`)

    return new Response(JSON.stringify(summary, null, 2), {
      headers: { 'Content-Type': 'application/json' }
    })

  } catch (error) {
    const totalDuration = ((Date.now() - pipelineStart) / 1000).toFixed(2)

    console.error('❌ Pipeline failed:', error.message)

    return new Response(
      JSON.stringify({
        success: false,
        error: error.message,
        duration: `${totalDuration}s`
      }, null, 2),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }
    )
  }
})
