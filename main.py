# main.py
from youtube_fetcher import get_videos_this_month, extract_guests_from_videos
from doc_generator import generate_doc
from datetime import datetime


def main():
    now = datetime.now()
    print(f"🎬 머니올라 출연료 집행 의뢰서 생성기")
    print(f"📅 조회 기간: {now.year}년 {now.month}월 1일 ~ {now.day}일\n")

    print("🔍 유튜브 영상 검색 중...")
    videos = get_videos_this_month()

    if not videos:
        print("⚠️  이번 달 업로드된 영상이 없습니다.")
        return

    print(f"📹 총 {len(videos)}개 영상 발견\n")
    for v in videos:
        print(f"  [{v['date']}] {v['title'][:50]}")

    print("\n👤 출연자 추출 중... (썸네일 + 첫프레임 + 제목 분석)\n")
    guest_data = extract_guests_from_videos(videos)

    print("\n📋 최종 출연자 목록:")
    print("-" * 60)
    for g in guest_data:
        guest_name = g['guest'] if g['guest'] else "⚠️ 미확인"
        print(f"  [{g['date']}] {guest_name:<10} ← {g['title'][:35]}")
    print("-" * 60)

    print("\n📄 Word 문서 생성 중...")
    filepath = generate_doc(guest_data)

    print(f"\n✅ 완료! 생성된 파일: {filepath}")
    print("💡 미확인 항목은 문서에서 직접 수정해주세요.")


if __name__ == "__main__":
    main()
