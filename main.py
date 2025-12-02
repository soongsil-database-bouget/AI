import os
import json
import base64
import uuid
import requests
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
YOUR_SITE_URL = os.getenv("YOUR_SITE_URL", "http://localhost:8001")
YOUR_SITE_NAME = "BouquetService"
TARGET_MODEL = "google/gemini-3-pro-image-preview"

# google/gemini-2.5-flash-image-preview 
# openai/gpt-5-image-mini
# google/gemini-3-pro-image-preview 

RESULT_DIR = "static/results"
os.makedirs(RESULT_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.post("/api/composite-bouquet")
async def composite_bouquet(
    user_image: UploadFile = File(...),    
    bouquet_image: UploadFile = File(...), 
):
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="API Key가 설정되지 않았습니다.")

    print(f">>> 파일 업로드 요청 수신: {user_image.filename}, {bouquet_image.filename}")

    try:
        # 유저 이미지 읽기
        user_bytes = await user_image.read()
        user_b64 = base64.b64encode(user_bytes).decode("utf-8")
        
        # 부케 이미지 읽기
        bouquet_bytes = await bouquet_image.read()
        bouquet_b64 = base64.b64encode(bouquet_bytes).decode("utf-8")

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
            "Referer": YOUR_SITE_URL,
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
            raise HTTPException(status_code=500, detail=f"Gemini API Error: {res.text}")
            
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

        filename = f"{uuid.uuid4()}.png"
        save_path = os.path.join(RESULT_DIR, filename)

        # 결과가 Base64인 경우
        if final_data.startswith("data:"):
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(final_data.split(",")[1]))

        # 결과가 URL인 경우
        elif final_data.startswith("http"):
            img_res = requests.get(final_data)
            with open(save_path, "wb") as f:
                f.write(img_res.content)

        # 결과 URL 반환 
        full_image_url = f"{YOUR_SITE_URL}/static/results/{filename}"
        
        print(f">>> 성공! 결과 반환: {full_image_url}")

        return {
            "status": "success",
            "result_image_url": full_image_url,
            "message": "합성 완료"
        }

    except Exception as e:
        print(f"에러 발생: {e}")
        raise HTTPException(status_code=500, detail=str(e))