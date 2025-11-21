import requests
import json
import base64
from IPython.display import display, HTML, Image as ColabImage
from google.colab import files

# 1. 설정 (OpenRouter API 키)
OPENROUTER_API_KEY = "api 키 입력"
YOUR_SITE_URL = "https://colab.research.google.com" # Colab 환경
YOUR_SITE_NAME = "ColabBouquetService"
TARGET_MODEL = "아래 모델 중 선택"

# openai/gpt-5-image-mini : 완전 재구성, 완성도 굿, 비용 중
# google/gemini-2.5-flash-image-preview : 원본 유지, 완성도 흠.., 비용 하
# google/gemini-3-pro-image-preview : 가장 굿, 비용 상

def upload_and_generate_with_ai_studio_format():
    print(">>> 원본 인물 이미지 업로드")
    uploaded_person = files.upload()
    if not uploaded_person:
        print("인물 이미지 업로드 취소")
        return

    person_file_name = list(uploaded_person.keys())[0]
    with open(person_file_name, "rb") as f:
        person_image_base64 = base64.b64encode(f.read()).decode("utf-8")
    person_image_data_url = f"data:image/jpeg;base64,{person_image_base64}"

    print(f"\n>>> 합성할 부케 이미지 업로드")
    uploaded_bouquet = files.upload()
    if not uploaded_bouquet:
        print("부케 이미지 업로드 취소")
        return

    bouquet_file_name = list(uploaded_bouquet.keys())[0]
    with open(bouquet_file_name, "rb") as f:
        bouquet_image_base64 = base64.b64encode(f.read()).decode("utf-8")
    bouquet_image_data_url = f"data:image/jpeg;base64,{bouquet_image_base64}"

    print(f"\n>>> [{TARGET_MODEL}] 모델로 이미지 생성 요청 중...")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": YOUR_SITE_URL,
        "X-Title": YOUR_SITE_NAME,
    }

    # 두 이미지를 합성하여 자연스러운 결과물을 만들도록 지시
    master_prompt = (
        "Combine the two provided images. "
        "The first image shows a person (bride). "
        "The second image shows a bouquet. "
        "Naturally integrate the bouquet from the second image into the hands of the person in the first image. "
	"Automatically and appropriately scale the bouquet to create the most visually balanced and natural composition, based on the bride's proportions and the overall scene. "
        "Ensure the lighting, shadows, and overall style are photorealistic and seamless. "
        "Maintain the original pose and background of the person. "
        "The final image should be a high-quality, elegant wedding photo."
    )

    payload = {
        "model": TARGET_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": master_prompt},               # 1. 마스터 프롬프트
                    {"type": "image_url", "image_url": {"url": person_image_data_url}}, # 2. 인물 이미지
                    {"type": "image_url", "image_url": {"url": bouquet_image_data_url}}  # 3. 부케 이미지
                ]
            }
        ]
    }

    try:
        res = requests.post(url, headers=headers, data=json.dumps(payload))

        if res.status_code == 200:
            result = res.json()
            image_output_data = None
            if 'choices' in result and result['choices']:
                msg = result['choices'][0]['message']
                if 'images' in msg:
                    image_output_data = msg['images'][0]['image_url']['url']
                elif 'content' in msg and msg['content'].startswith("data:"):
                    image_output_data = msg['content']
                elif 'content' in msg and msg['content'].startswith("http"):
                    image_output_data = msg['content']

            if image_output_data:
                print("\n이미지 생성 성공")
                if image_output_data.startswith("data:image"):
                    display(HTML(f'<img src="{image_output_data}" style="max-width:800px; height:auto;">'))
                elif image_output_data.startswith("http"):
                    display(ColabImage(url=image_output_data, width=800))
                else:
                    print("알 수 없는 이미지 출력 형식:", image_output_data[:100])
            else:
                print("이미지 데이터가 응답에서 발견되지 않았음")
                print("전체 응답:", json.dumps(result, indent=2))

        else:
            print(f"API 호출 실패 (코드 {res.status_code}): {res.text}")

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    upload_and_generate_with_ai_studio_format()