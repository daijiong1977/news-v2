// Supabase Edge Function: Send Email via AWS SES
// Deployed at: https://lfknsvavhiqrsasdfyrs.supabase.co/functions/v1/send-email

import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

// AWS SES SDK for Deno
import { SESClient, SendEmailCommand } from "npm:@aws-sdk/client-ses@3"

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    // Get Supabase client
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_ANON_KEY') ?? '',
      {
        global: {
          headers: { Authorization: req.headers.get('Authorization')! },
        },
      }
    )

    // AUTHENTICATION SUPPORT
    // Option 1: Supabase Anon Key (Authorization + apikey headers must match)
    // Option 2: Supabase User Token (Authorization: Bearer <user-jwt>)
    // Option 3: Legacy API Key (X-API-Key header) - for backward compatibility

    const authHeader = req.headers.get('Authorization')
    const apikeyHeader = req.headers.get('apikey')
    const legacyApiKeyHeader = req.headers.get('X-API-Key')

    let authenticated = false
    let username = 'unknown'

    // Check for anon key authentication
    // Both Authorization and apikey headers must be present and match each other
    if (authHeader && apikeyHeader && authHeader.startsWith('Bearer ')) {
      const tokenFromAuth = authHeader.replace('Bearer ', '')

      // If both headers match, accept as anon key authentication
      if (tokenFromAuth === apikeyHeader) {
        authenticated = true
        username = 'public-anon'
        console.log('✅ Authenticated via Supabase anon key (headers match)')
      }
    }

    // Try Supabase user authentication (if not already authenticated)
    if (!authenticated && authHeader && authHeader.startsWith('Bearer ')) {
      try {
        const { data: { user }, error: authError } = await supabaseClient.auth.getUser()

        if (!authError && user) {
          authenticated = true
          username = user.email || user.id
          console.log('✅ Authenticated via Supabase Auth:', username)
        }
      } catch (e) {
        // Ignore auth errors, will fall through to other methods
        console.log('Supabase auth check failed:', e.message)
      }
    }

    // Fall back to Legacy API Key (for backward compatibility)
    if (!authenticated && legacyApiKeyHeader) {
      // Parse API key (format: key_id.secret)
      const [keyId, secret] = legacyApiKeyHeader.split('.')

      if (keyId && secret) {
        // Verify API key from database
        const { data: keyData, error: keyError } = await supabaseClient
          .from('api_keys')
          .select('*')
          .eq('key_id', keyId)
          .is('revoked_at', null)
          .single()

        if (!keyError && keyData) {
          authenticated = true
          username = keyData.username
          console.log('⚠️  Authenticated via Legacy API Key (deprecated):', username)
        }
      }
    }

    // Reject if no authentication method succeeded
    if (!authenticated) {
      return new Response(
        JSON.stringify({
          error: 'Authentication required',
          message: 'Provide matching Authorization: Bearer <anon_key> and apikey: <anon_key> headers, or a valid user token'
        }),
        { status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }

    // Parse request body
    const { to_email, subject, message, from_name } = await req.json()

    if (!to_email || !subject || !message) {
      return new Response(
        JSON.stringify({ error: 'Missing required fields: to_email, subject, message' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }

    // Get AWS SES credentials from secrets using service role client
    const serviceClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    )

    const { data: awsAccessKey } = await serviceClient.rpc('get_secret', { secret_name: 'AWS_ACCESS_KEY_ID' })
    const { data: awsSecretKey } = await serviceClient.rpc('get_secret', { secret_name: 'AWS_SECRET_ACCESS_KEY' })
    const { data: awsRegion } = await serviceClient.rpc('get_secret', { secret_name: 'AWS_REGION' })
    const { data: fromEmail } = await serviceClient.rpc('get_secret', { secret_name: 'FROM_EMAIL' })

    if (!awsAccessKey || !awsSecretKey || !awsRegion || !fromEmail) {
      console.error('AWS SES credentials missing:', { awsAccessKey, awsSecretKey, awsRegion, fromEmail })
      return new Response(
        JSON.stringify({ error: 'AWS SES not configured', details: 'One or more AWS credentials are missing' }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }

    // Create SES client
    const sesClient = new SESClient({
      region: awsRegion,
      credentials: {
        accessKeyId: awsAccessKey,
        secretAccessKey: awsSecretKey,
      },
    })

    // Send email
    const command = new SendEmailCommand({
      Source: from_name ? `${from_name} <${fromEmail}>` : fromEmail,
      Destination: {
        ToAddresses: [to_email],
      },
      Message: {
        Subject: {
          Data: subject,
        },
        Body: {
          Text: {
            Data: message,
          },
        },
      },
    })

    const response = await sesClient.send(command)

    return new Response(
      JSON.stringify({
        success: true,
        message: `Email sent to ${to_email}`,
        email_id: response.MessageId,
        sent_by: username
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200,
      },
    )

  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 500,
      },
    )
  }
})
