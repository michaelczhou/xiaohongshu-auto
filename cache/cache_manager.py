"""
缓存管理器 - 管理任务历史
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class CacheManager:
    """任务缓存管理器"""
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = Path(__file__).parent
        self.cache_dir = Path(cache_dir)
        self.history_file = self.cache_dir / "task_history.json"
        self._history: Optional[List[Dict]] = None
    
    def _load_history(self) -> List[Dict]:
        """加载历史记录"""
        if self._history is not None:
            return self._history
        
        if self.history_file.exists():
            with open(self.history_file, 'r', encoding='utf-8') as f:
                self._history = json.load(f)
        else:
            self._history = []
        
        return self._history
    
    def _save_history(self) -> None:
        """保存历史记录"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self._history, f, indent=2, ensure_ascii=False)
    
    def add_task(self, task: Dict) -> str:
        """添加任务"""
        history = self._load_history()
        task_id = f"task_{len(history)}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        task["id"] = task_id
        task["created_at"] = datetime.now().isoformat()
        task["status"] = "pending"
        history.append(task)
        self._history = history
        self._save_history()
        return task_id
    
    def update_task(self, task_id: str, updates: Dict) -> bool:
        """更新任务"""
        history = self._load_history()
        for i, task in enumerate(history):
            if task["id"] == task_id:
                history[i].update(updates)
                history[i]["updated_at"] = datetime.now().isoformat()
                self._history = history
                self._save_history()
                return True
        return False
    
    def get_history(self, limit: int = 50, status: str = None) -> List[Dict]:
        """获取历史记录"""
        history = self._load_history()
        if status:
            history = [t for t in history if t.get("status") == status]
        return history[-limit:][::-1]  # 最新的在前
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        history = self._load_history()
        total = len(history)
        success = len([t for t in history if t.get("status") == "success"])
        failed = len([t for t in history if t.get("status") == "failed"])
        pending = len([t for t in history if t.get("status") == "pending"])
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "pending": pending
        }


# 全局缓存管理器实例
cache_manager = CacheManager()
