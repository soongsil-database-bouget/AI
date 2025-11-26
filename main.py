import os
import json
import base64
import uuid
import requests
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# 배포된 서버의 주소 - 나중에 팀원이 알려주는 실제 도메인/IP로 변경 필요
YOUR_SITE_URL = "http://localhost:8000" 
YOUR_SITE_NAME = "BouquetService"
TARGET_MODEL = "google/gemini-3-pro-image-preview"

# google/gemini-2.5-flash-image-preview 
# openai/gpt-5-image-mini
# google/gemini-3-pro-image-preview 

RESULT_DIR = "static/results"
os.makedirs(RESULT_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class CompositeRequest(BaseModel):
    user_image_url: str
    bouquet_image_url: str
    prompt_option: str = "standard and natural size"

@app.post("/api/composite-bouquet")
async def composite_bouquet(request: CompositeRequest):
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="API Key가 설정되지 않았습니다.")

    print(f">>> 요청 수신: {request.user_image_url}")

    try:
        # URL -> Base64 변환 함수
        def url_to_base64(url):
            try:
                res = requests.get(url, timeout=10)
                if res.status_code != 200:
                    raise Exception(f"다운로드 실패: {res.status_code}")
                return base64.b64encode(res.content).decode("utf-8")
            except Exception as e:
                raise Exception(f"이미지 처리 중 오류: {str(e)}")

        user_b64 = url_to_base64(request.user_image_url)
        bouquet_b64 = url_to_base64(request.bouquet_image_url)

        # Gemini 프롬프트
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
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{user_b64}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{bouquet_b64}"}}
                    ]
                }
            ]
        }

        res = requests.post(url, headers=headers, data=json.dumps(payload))
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail=f"AI 모델 오류: {res.text}")
            
        result = res.json()
        
        # 결과 파싱
        final_data = None
        if 'choices' in result and result['choices']:
            content = result['choices'][0]['message']
            if 'images' in content:
                final_data = content['images'][0]['image_url']['url']
            elif 'content' in content:
                final_data = content['content']
        
        if not final_data:
             raise HTTPException(status_code=500, detail="이미지 생성 데이터 없음")

        # 파일 저장
        filename = f"{uuid.uuid4()}.png"
        save_path = os.path.join(RESULT_DIR, filename)

        if final_data.startswith("data:"):
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(final_data.split(",")[1]))
        elif final_data.startswith("http"):
            img_res = requests.get(final_data)
            with open(save_path, "wb") as f:
                f.write(img_res.content)

        # 결과 URL 반환 (EC2 서버 주소로 바꿔야 함)
        # 일단은 상대 경로로 주거나, 나중에 EC2 IP를 알면 그걸로 변경
        return {
            "status": "success",
            "result_image_url": f"/static/results/{filename}" 
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))