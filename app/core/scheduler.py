"""앱 프로세스 내부에서 도는 스케줄러. 신규 systemd 유닛 없이 기존 uvicorn 프로세스
안에서만 동작한다 (서버 설정 변경 없음).

VXvue 사양서 동기화는 크롤러가 Windows 전용이라, 이 스케줄러가 Ubuntu 서버에서 돌 때는
매일 시각이 되면 시도는 하되 `is_available_on_this_host()`가 False이면 조용히 건너뛴다.
실제 자동 실행은 크롤러가 있는 Windows PC의 작업 스케줄러(scripts/sync_vxvue_spec.py)가 담당한다.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.core.product_config import load_product_config
from app.core.storage import Storage

logger = logging.getLogger("regression_analyzer")
_scheduler: BackgroundScheduler | None = None


def _sync_specification_job() -> None:
    from app.sync.vxvue_spec import is_available_on_this_host, run

    storage = Storage()
    product = "VXvue"
    if not is_available_on_this_host():
        logger.info("scheduled_sync_skipped product=%s reason=크롤러_output_폴더_접근_불가", product)
        return
    if storage.is_sync_running(product, "specification"):
        logger.info("scheduled_sync_skipped product=%s reason=이미_실행_중", product)
        return
    sync_id = storage.sync_start(product, "specification", "alm_crawler")
    try:
        port = get_settings().get("app.port", 12000)
        result = run(f"http://127.0.0.1:{port}")
        storage.sync_finish(sync_id, result["status"], result["detail"])
        logger.info("scheduled_sync_finished product=%s status=%s detail=%s", product, result["status"], result["detail"])
    except Exception as exc:
        storage.sync_finish(sync_id, "FAILED", str(exc))
        logger.exception("scheduled_sync_failed product=%s", product)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    config = load_product_config("vxvue")
    schedule_time = (config.sync.schedule_time if config else "07:30") or "07:30"
    day_of_week = (config.sync.day_of_week if config else "mon") or "mon"
    hour, _, minute = schedule_time.partition(":")
    scheduler.add_job(
        _sync_specification_job,
        CronTrigger(day_of_week=day_of_week, hour=int(hour or 7), minute=int(minute or 30), timezone="Asia/Seoul"),
        id="sync_vxvue_specification",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("scheduler_started day_of_week=%s schedule_time=%s timezone=Asia/Seoul", day_of_week, schedule_time)
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
