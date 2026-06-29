# youtube_fetcher.py
from googleapiclient.discovery import build
from datetime import datetime, timezone
import os
import re
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")


def get_videos_this_month():
    """
    이번 달 1일부터 오늘까지 업로드된 영상 목록을 가져옵니다.
    반환값: [{"date": "06/03", "title": "영상제목", "description": "설명"}, ...]
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

            videos.append({
                "date": month_day,
                "title": snippet["title"],
                "description": snippet.get("description", ""),
                "video_id": item["id"]["videoId"],
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    # 날짜 오름차순 정렬
    videos.sort(key=lambda x: x["date"])
    return videos


def extract_guests_from_videos(videos):
    """
    영상 제목/설명에서 출연자 이름을 추출합니다.
    패턴: [이름], 출연: 이름, ㅣ이름 직책 등
    반환값: [{"date": "06/03", "title": "...", "guest": "이름"}, ...]
    """
    patterns = [
        r"출연\s*[:：]\s*([가-힣]{2,4})",
        r"\[([가-힣]{2,4})\]",
        r"ㅣ\s*([가-힣]{2,4})\s*(?:교수|박사|대표|위원|기자|연구원|팀장|이사|본부장|소장|원장|작가|PD|pd)?",
        r"([가-힣]{2,4})\s*(?:교수|박사|대표|위원|기자|연구원|팀장|이사|본부장|소장|원장|작가)",
    ]

    guest_list = []

    for video in videos:
        combined_text = video["title"] + " " + video["description"][:300]
        found_guest = ""
        for pattern in patterns:
            match = re.search(pattern, combined_text)
            if match:
                found_guest = match.group(1)
                break

        guest_list.append({
            "date": video["date"],
            "title": video["title"],
            "guest": found_guest,
        })

    return guest_list
