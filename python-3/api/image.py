from openai import OpenAI

client = OpenAI(
      api_key="eyJ0eXxx",  # 此处传token，不带Bearer
    base_url="https://chat.intern-ai.org.cn/api/v1/",
)

response = client.chat.completions.create(
    model="intern-s1",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "图片里有什么？"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
                    },
                },
            ],
        }
    ],
    extra_body={"thinking_mode": True},
)

print(response.choices[0].message.content)