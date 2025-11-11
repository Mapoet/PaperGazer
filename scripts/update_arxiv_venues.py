#!/usr/bin/env python3
"""
更新数据库中 arXiv 论文的 venue 字段
将主分类设置为 venue
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config
from papergazer.store.db import init_db, get_session, PaperItem

def main():
    # 加载配置
    config_path = project_root / "configs" / "config.test.yaml"
    if not config_path.exists():
        config_path = project_root / "configs" / "config.yaml"
    
    config = load_config(config_path)
    init_db(config.store.db_path)
    
    session = get_session()
    
    try:
        # 查询所有 arXiv 论文且 venue 为空或为 "None" 的记录
        arxiv_papers = session.query(PaperItem).filter(
            PaperItem.source == "arxiv",
            (PaperItem.venue == None) | (PaperItem.venue == "") | (PaperItem.venue == "None")
        ).all()
        
        print(f"找到 {len(arxiv_papers)} 篇需要更新 venue 的 arXiv 论文")
        
        updated_count = 0
        
        for paper in arxiv_papers:
            # 由于数据库中没有存储分类信息，统一使用 "arXiv" 作为 venue
            # 新抓取的论文会自动包含详细的分类信息
            paper.venue = "arXiv"
            updated_count += 1
            
            if updated_count <= 5:
                print(f"  更新: {paper.identifier} -> {paper.venue}")
        
        # 提交更改
        session.commit()
        
        print(f"\n更新完成:")
        print(f"  - 更新论文数: {updated_count} 篇")
        print(f"  - 所有论文的 venue 已设置为 'arXiv'")
        print(f"  - 新抓取的论文将自动包含详细分类信息（如 'arXiv [cs.AI]'）")
        
    except Exception as e:
        session.rollback()
        print(f"错误: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()

