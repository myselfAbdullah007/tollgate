import os
from openai import OpenAI

client = OpenAI(base_url=os.getenv('TOLLGATE_BASE_URL', 'http://localhost:8187/v1'),
                api_key=os.getenv('TOLLGATE_API_KEY', 'tg_live_demo_tollgate_local_only'))
stream = client.chat.completions.create(
    model='smart', stream=True,
    messages=[{'role': 'user', 'content': 'Email ali@example.com a refund update'}],
    extra_headers={'X-Tollgate-Customer': 'cus_acme'},
)
for chunk in stream:
    if chunk.choices:
        print(chunk.choices[0].delta.content or '', end='', flush=True)
print()
