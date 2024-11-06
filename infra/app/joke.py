import os
import openai
import pulumi_esc_sdk as esc

access_token = os.getenv("PULUMI_ACCESS_TOKEN")
config = esc.Configuration(access_token=access_token)
client_esc = esc.EscClient(config)

env, values, yaml = client_esc.open_and_read_environment("upstarts", "luke", "joker-app")
open_api_key = values["environmentVariables"].get("OPENAI_API_KEY")

def tell_joke():
    client = openai.OpenAI(api_key=open_api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.8,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": 
                """
                Tell me a short joke about cloud infrastructure.  
                Don't respond to this comment - just tell the joke!
                """
            }
        ]
    )
    joke = response.choices[0].message.content or ""
    return joke.strip()

if __name__ == "__main__":
    print(tell_joke())