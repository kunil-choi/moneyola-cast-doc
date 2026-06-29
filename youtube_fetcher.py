# youtube_fetcher.py
from googleapiclient.discovery import build
from datetime import datetime, timezone
import os
import re
import requests
import anthropic
import base64
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def get_videos_this_month():
    """
    이번 달 1일부터 오늘까지 업로드된 영상 목록을 가져옵니다.
    """
    youtube = build("youtube", "v3", developerKey=API_KEY)

    today = datetime.now(timezone.utc)
    first_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    published_after = first_of_month.strftime("%Y-%m-%dT%H:%M:%SZ")
    published_before = today.strftime("%Y-%m-%dT%H:%M:%SZ")

    videos = []
    next_page_token = None

    while True:
        request = youtube.search().list(
            part="snippet",
            channelId=CHANNEL_ID,
            publishedAfter=published_after,
            publishedBefore=published_before,
            maxResults=50,
            order="date",
            type="video",
            pageToken=next_page_token,
        )
        response = request.execute()

        for item in response.get("items", []):
            snippet = item["snippet"]
            pub_date = snippet["publishedAt"][:10]  # "YYYY-MM-DD"
            month_day = pub_date[5:].replace("-", "/")  # "MM/DD"

            # 요일 계산
            dt = datetime.strptime(pub_date, "%Y-%m-%d")
            weekdays = ["월", "화", "수", "목", "금", "토", "일"]
            weekday = weekdays[dt.weekday()]
            date_with_day = f"{month_day} ({weekday})"

            # 썸네일 URL (maxres > high > medium 순으로 최고화질 선택)
            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = (
                thumbnails.get("maxres", {}).get("url")
                or thumbnails.get("high", {}).get("url")
                or thumbnails.get("medium", {}).get("url")
                or ""
            )

            videos.append({
                "date": date_with_day,
                "title": snippet["title"],
                "description": snippet.get("description", ""),
                "video_id": item["id"]["videoId"],
                "thumbnail_url": thumbnail_url,
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    videos.sort(key=lambda x: x["date"])
    return videos


def image_url_to_base64(url: str) -> str | None:
    """이미지 URL을 base64로 변환합니다."""
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return base64.standard_b64encode(res.content).decode("utf-8")
    except Exception:
        pass
    return None


def get_first_frame_url(video_id: str) -> str:
    """
    YouTube 영상의 첫 프레임 이미지 URL을 반환합니다.
    YouTube는 자동으로 여러 프레임 썸네일을 제공합니다.
    """
    # YouTube 자동 생성 프레임 이미지 (0번 = 첫 장면)
    return f"https://img.youtube.com/vi/{video_id}/0.jpg"


def extract_name_with_claude(title: str, thumbnail_b64: str | None, frame_b64: str | None) -> str:
    """
    Claude Vision으로 썸네일/첫프레임 이미지와 제목을 분석해서 출연자 이름을 추출합니다.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # 이미지 콘텐츠 구성
    content = []

    if thumbnail_b64:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": thumbnail_b64,
            }
        })
        content.append({
            "type": "text",
            "text": "위 이미지는 유튜브 영상의 썸네일입니다."
        })

    if frame_b64:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": frame_b64,
            }
        })
        content.append({
            "type": "text",
            "text": "위 이미지는 유튜브 영상의 첫 번째 프레임입니다."
        })

    content.append({
        "type": "text",
        "text": f"""영상 제목: {title}

위 정보(썸네일 이미지, 첫 프레임 이미지, 영상 제목)를 보고 이 영상에 출연한 게스트(외부 출연자)의 한국어 이름을 추출해주세요.

규칙:
1. 반드시 실제 출연자(게스트)의 이름만 추출하세요.
2. KBS 머니올라 채널의 고정 진행자나 채널 자체 코너명은 제외하세요.
3. 이름이 영어로 표기되어 있으면 한국어 이름으로 변환하세요.
4. 출연자가 여러 명이면 쉼표로 구분해서 모두 나열하세요.
5. 출연자를 찾을 수 없으면 반드시 "없음"이라고만 답하세요.
6. 이름 외에 다른 설명은 절대 포함하지 마세요.

답변 형식: 이름만 (예: 홍길동 또는 홍길동, 김철수 또는 없음)"""
    })

    try:
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=100,
            messages=[{"role": "user", "content": content}]
        )
        result = message.content[0].text.strip()
        # "없음" 또는 빈값 처리
        if result in ["없음", "없음.", "None", "N/A", ""]:
            return ""
        return result
    except Exception as e:
        print(f"  ⚠️ Claude API 오류: {e}")
        return ""


def extract_guests_from_videos(videos):
    """
    각 영상별로 3단계로 출연자 이름을 추출합니다.
    1단계: 썸네일 이미지 → Claude Vision
    2단계: 첫 프레임 이미지 → Claude Vision
    3단계: 제목만으로 Claude 텍스트 분석
    """
    guest_list = []

    for i, video in enumerate(videos):
        print(f"  [{i+1}/{len(videos)}] {video['date']} | {video['title'][:45]}...")

        # ── 1단계: 썸네일 이미지 분석
        thumbnail_b64 = None
        if video["thumbnail_url"]:
            print(f"    📸 썸네일 분석 중...")
            thumbnail_b64 = image_url_to_base64(video["thumbnail_url"])

        # ── 2단계: 첫 프레임 이미지 분석
        frame_b64 = None
        first_frame_url = get_first_frame_url(video["video_id"])
        print(f"    🎬 첫 프레임 분석 중...")
        frame_b64 = image_url_to_base64(first_frame_url)

        # ── Claude Vision으로 통합 분석
        print(f"    🤖 Claude 분석 중...")
        guest_name = extract_name_with_claude(
            title=video["title"],
            thumbnail_b64=thumbnail_b64,
            frame_b64=frame_b64,
        )

        if guest_name:
            print(f"    ✅ 출연자: {guest_name}")
        else:
            print(f"    ⚠️  출연자 미확인")

        guest_list.append({
            "date": video["date"],
            "title": video["title"],
            "guest": guest_name,
        })

    return guest_list
