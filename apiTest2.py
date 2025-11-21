import os
import json
import base64
import uuid
import requests
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# 1. 설정
OPENROUTER_API_KEY = "api 입력" 
YOUR_SITE_URL = "http://localhost:8000"
YOUR_SITE_NAME = "BouquetService"
TARGET_MODEL = "google/gemini-2.5-flash-image-preview" 

# google/gemini-2.5-flash-image-preview : 원본 유지, 완성도 흠.., 비용 하
# openai/gpt-5-image-mini : 완전 재구성, 완성도 굿, 비용 중
# google/gemini-3-pro-image-preview : 가장 굿, 비용 상


# 결과 이미지 저장 경로
RESULT_DIR = "static/results"
os.makedirs(RESULT_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. 엔드포인트 정의
@app.post("/api/composite-bouquet")
async def composite_bouquet(
    user_image: UploadFile = File(...),    # 첫 번째 파일 (유저)
    bouquet_image: UploadFile = File(...), # 두 번째 파일 (부케)
):
    print(f">>> 합성 요청 받음: {user_image.filename} + {bouquet_image.filename}")

    # 1) 업로드된 파일을 읽어서 Base64로 변환
    # 유저 이미지 처리
    user_bytes = await user_image.read()
    user_b64 = base64.b64encode(user_bytes).decode("utf-8")
    user_data_url = f"data:image/jpeg;base64,{user_b64}"

    # 부케 이미지 처리
    bouquet_bytes = await bouquet_image.read()
    bouquet_b64 = base64.b64encode(bouquet_bytes).decode("utf-8")
    bouquet_data_url = f"data:image/jpeg;base64,{bouquet_b64}"

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
                    {"type": "image_url", "image_url": {"url": user_data_url}},    # 이미지 1
                    {"type": "image_url", "image_url": {"url": bouquet_data_url}}   # 이미지 2
                ]
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"API 에러: {response.text}")
            
        result = response.json()

        # 4) 결과 이미지 파싱 및 저장
        final_image_data = None
        if 'choices' in result and result['choices']:
            content = result['choices'][0]['message']
            if 'images' in content:
                final_image_data = content['images'][0]['image_url']['url']
            elif 'content' in content:
                final_image_data = content['content']
        
        if not final_image_data:
            raise HTTPException(status_code=500, detail="이미지 생성 실패")

        # 파일 저장
        filename = f"{uuid.uuid4()}.png"
        save_path = os.path.join(RESULT_DIR, filename)

        # Base64 디코딩 저장
        if final_image_data.startswith("data:"):
            b64_str = final_image_data.split(",")[1]
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(b64_str))
        # URL 다운로드 저장
        elif final_image_data.startswith("http"):
            img_res = requests.get(final_image_data)
            with open(save_path, "wb") as f:
                f.write(img_res.content)

        # 5) 결과 URL 반환
        return {
            "status": "success",
            "original_user_file": user_image.filename,
            "original_bouquet_file": bouquet_image.filename,
            "result_image_url": f"/static/results/{filename}"
        }

    except Exception as e:
        print(f"에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))