from openai import OpenAI
client = OpenAI(
      api_key="eyJ0eXxx",  # 此处传token，不带Bearer
    base_url="https://chat.intern-ai.org.cn/api/v1/",
)

completion = client.chat.completions.create(
    model="intern-s1",
    messages=[
        {
            "role": "user",
            "content": "写一个关于独角兽的睡前故事，一句话就够了。"
        }
    ]
)

print(completion.choices[0].message.content)