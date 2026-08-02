# main.py
import os
import calendar
from youtube_fetcher import get_videos_this_month, extract_guests_from_videos
from doc_generator import generate_doc
from datetime import datetime


def main():
    now = datetime.now()

    year_env = os.getenv("TARGET_YEAR", "").strip()
    month_env = os.getenv("TARGET_MONTH", "").strip()
    year = int(year_env) if year_env else None
    month = int(month_env) if month_env else None

    display_year = year or now.year
    display_month = month or now.month
    last_day = now.day if (display_year, display_month) == (now.year, now.month) \
        else calendar.monthrange(display_year, display_month)[1]

    print(f"🎬 머니올라 출연료 집행 의뢰서 생성기")
    print(f"📅 조회 기간: {display_year}년 {display_month}월 1일 ~ {last_day}일\n")

    print("🔍 유튜브 영상 검색 중...")
    videos = get_videos_this_month(year, month)

    if not videos:
        print("⚠️  해당 월에 업로드된 영상이 없습니다.")
        return

    print(f"📹 총 {len(videos)}개 영상 발견\n")
    for v in videos:
        print(f"  [{v['date']}] {v['title'][:50]}")

    print("\n👤 출연자 추출 중... (썸네일 + 첫프레임 + 제목 분석)\n")
    guest_data = extract_guests_from_videos(videos)

    print("\n📋 최종 출연자 목록:")
    print("-" * 60)
    for g in guest_data:
        guest_name = g['guest'] if g['guest'] else "⚠️ 인식실패"
        print(f"  [{g['date']}] {guest_name:<10} ← {g['title'][:35]}")
    print("-" * 60)

    print("\n📄 Word 문서 생성 중...")
    filepath = generate_doc(guest_data, year=year, month=month)

    print(f"\n✅ 완료! 생성된 파일: {filepath}")
    print("💡 빨간색 '인식실패' 항목은 문서에서 직접 수정해주세요.")


if __name__ == "__main__":
    main()
