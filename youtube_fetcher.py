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
            pub_date = snippet["publishedAt"][:10]
            month_day = pub_date[5:].replace("-", "/")

            videos.append({
                "date": month_day,
                "title": snippet["title"],
                "description": snippet.get("description", ""),
                "video_id": item["id"]["videoId"],
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    videos.sort(key=lambda x: x["date"])
    return videos


def extract_guests_from_videos(videos):
    """
    머니올라 영상 제목에서 출연자 이름을 추출합니다.

    머니올라 제목 패턴 예시:
      한국어: [저자 강환국], [유신익 박사], [염블리의 비밀노트], ㅣ염승환
      영어:   [Author Kang Hwan-kook], [Dr. Shin-ik Yoo], [Yeomvely]
    """

    # ── 영문 이름 → 한국어 이름 매핑 테이블
    name_map = {
        # 영문 → 한국어
        "kang hwan": "강환국",
        "kang hwan-kook": "강환국",
        "hwankook": "강환국",
        "shin-ik yoo": "유신익",
        "shin ik yoo": "유신익",
        "yoo shin": "유신익",
        "yeomvely": "염승환",
        "yeom-vely": "염승환",
        "yeom vely": "염승환",
        "byung-seo jeon": "전병서",
        "byungseo jeon": "전병서",
        "jeon byung": "전병서",
        "woong-hwan yoo": "유웅환",
        "yoo woong": "유웅환",
        "seo dae-il": "서대일",
        "dae-il seo": "서대일",
        "seong-jin oh": "오성진",
        "oh seong": "오성진",
        "gun-young oh": "오건영",
        "oh gun": "오건영",
        "park hyun-wook": "박현욱",
        "hyun-wook park": "박현욱",
        "yoon sung-ho": "윤성호",
        "sung-ho yoon": "윤성호",
        "seonwoo": "선우",
    }

    # ── 한국어 이름 추출 패턴
    korean_patterns = [
        # [저자 강환국], [강환국 저자] 형태
        r"\[(?:저자|작가|교수|박사|대표|위원|기자|연구원|이사|본부장|소장|원장|PD|애널리스트)?\s*([가-힣]{2,5})\s*(?:저자|작가|교수|박사|대표|위원|기자|연구원|이사|본부장|소장|원장|PD|애널리스트)?\]",
        # ㅣ염승환, | 염승환 형태
        r"[ㅣ|]\s*([가-힣]{2,4})\s*(?:교수|박사|대표|위원|기자|연구원|팀장|이사|본부장|소장|원장|작가|PD)?",
        # 출연: 홍길동
        r"출연\s*[:：]\s*([가-힣]{2,4})",
        # 영상 제목 맨 끝 대괄호 안 한글 이름
        r"\[([가-힣]{2,4})\s*(?:풀버전|full|1부|2부|3부)?\]",
        # 직책 앞에 오는 한글 이름
        r"([가-힣]{2,4})\s*(?:교수|박사|대표|위원|기자|연구원|팀장|이사|본부장|소장|원장|작가)",
    ]

    # ── 영문 이름 추출 패턴
    english_patterns = [
        # [Author Kang Hwan-kook], [Dr. Shin-ik Yoo] 형태
        r"\[(?:Author|Dr\.?|Prof\.?|CEO|Director|Analyst)?\s*([A-Za-z][a-z]+(?:[\s\-][A-Za-z][a-z]+)+)\]",
        # Part 1/2 with Author Name
        r"(?:with|by)\s+(?:Author\s+|Blogger\s+)?([A-Za-z][a-z]+(?:\s+[A-Za-z][a-z\-]+)+)",
        # 영문 이름 + 직책
        r"([A-Za-z][a-z]+(?:[\s\-][A-Za-z][a-z]+)+)\s+(?:CEO|CFO|CTO|Professor|Doctor|Analyst|Director)",
    ]

    guest_list = []

    for video in videos:
        title = video["title"]
        desc = video["description"][:300]
        combined = title + " " + desc
        found_guest = ""

        # 1차: 한국어 패턴으로 추출
        for pattern in korean_patterns:
            match = re.search(pattern, combined)
            if match:
                candidate = match.group(1).strip()
                # 노이즈 필터링 (코너명, 일반명사 제외)
                noise_words = {
                    "머니올라", "비욘드", "스페셜", "풀버전", "월간", "주간",
                    "염블리", "오건영", "전체", "최신", "요약", "하이라이트",
                    "비밀노트", "사파지존", "키나락스"
                }
                if candidate not in noise_words and len(candidate) >= 2:
                    found_guest = candidate
                    break

        # 2차: 영문 패턴으로 추출 후 한국어로 변환
        if not found_guest:
            for pattern in english_patterns:
                match = re.search(pattern, combined, re.IGNORECASE)
                if match:
                    eng_name = match.group(1).strip().lower()
                    # 매핑 테이블에서 찾기
                    for key, kor_name in name_map.items():
                        if key in eng_name or eng_name in key:
                            found_guest = kor_name
                            break
                if found_guest:
                    break

        guest_list.append({
            "date": video["date"],
            "title": video["title"],
            "guest": found_guest,
        })

    return guest_list
