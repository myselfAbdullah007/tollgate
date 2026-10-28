import OpenAI from 'openai';
const client = new OpenAI({baseURL: process.env.TOLLGATE_BASE_URL || 'http://localhost:8187/v1', apiKey: process.env.TOLLGATE_API_KEY || 'tg_live_demo_tollgate_local_only'});
const stream = await client.chat.completions.create({model: 'smart', stream: true, messages: [{role: 'user', content: 'Email ali@example.com a refund update'}]}, {headers: {'X-Tollgate-Customer': 'cus_acme'}});
for await (const chunk of stream) process.stdout.write(chunk.choices[0]?.delta?.content || '');
process.stdout.write('\n');
