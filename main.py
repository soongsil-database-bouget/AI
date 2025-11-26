import os
import json
import base64
import uuid
import requests
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

# 설정
OPENROUTER_API_KEY = "오픈 라우터 api key 입력"
YOUR_SITE_URL = "http://localhost:8000" # 배포 시 실제 서버 IP나 도메인으로 변경
YOUR_SITE_NAME = "BouquetService"
TARGET_MODEL = "google/gemini-3-pro-image-preview"

# google/gemini-2.5-flash-image-preview 
# openai/gpt-5-image-mini
# google/gemini-3-pro-image-preview 

RESULT_DIR = "static/results"
os.makedirs(RESULT_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# URL 문자열을 input으로
class CompositeRequest(BaseModel):
    user_image_url: str     # 예: "http://백엔드서버/images/user1.jpg"
    bouquet_image_url: str  # 예: "http://백엔드서버/images/bouquet3.jpg"
    prompt_option: str = "standard and natural size"

@app.post("/api/composite-bouquet")
async def composite_bouquet(request: CompositeRequest):
    print(f">>> URL 요청 수신: {request.user_image_url}, {request.bouquet_image_url}")

    try:
        def url_to_base64(url):
            res = requests.get(url)
            if res.status_code != 200:
                raise Exception(f"이미지 다운로드 실패: {url}")
            return base64.b64encode(res.content).decode("utf-8")

        user_b64 = url_to_base64(request.user_image_url)
        bouquet_b64 = url_to_base64(request.bouquet_image_url)

    # 2) 마스터 프롬프트 
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

    # 3) OpenRouter API 호출
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": YOUR_SITE_URL,
            "X-Title": YOUR_SITE_NAME,
        }
        
        payload = {
            "model": TARGET_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": master_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{user_b64}"}}, # 이미지 1
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{bouquet_b64}"}} # 이미지 2
                    ]
                }
            ]
        }

        print(">>> Gemini에게 생성 요청 중...")
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Gemini API Error: {response.text}")
            
        result = response.json()

        # 4) 결과 이미지 파싱 및 저장
        final_data = None
        if 'choices' in result and result['choices']:
            content = result['choices'][0]['message']
            if 'images' in content:
                final_data = content['images'][0]['image_url']['url']
            elif 'content' in content:
                final_data = content['content']
        
        if not final_data:
             raise HTTPException(status_code=500, detail="이미지 생성 실패")

        filename = f"{uuid.uuid4()}.png"
        save_path = os.path.join(RESULT_DIR, filename)

        if final_data.startswith("data:"):
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(final_data.split(",")[1]))
        elif final_data.startswith("http"):
            img_res = requests.get(final_data)
            with open(save_path, "wb") as f:
                f.write(img_res.content)

        # 결과 URL 반환
        full_image_url = f"{YOUR_SITE_URL}/static/results/{filename}"
        
        return {
            "status": "success",
            "result_image_url": full_image_url
        }

    except Exception as e:
        print(f"에러 발생: {e}")
        raise HTTPException(status_code=500, detail=str(e))