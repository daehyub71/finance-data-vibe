"""
프로젝트 구조 분석기 - Python 버전
Finance Data Vibe 프로젝트의 구조를 시각적으로 분석하고 표시
CSV 파일 스마트 그룹화 기능 포함
"""

import os
import sys
from pathlib import Path
import sqlite3
from datetime import datetime
from collections import defaultdict, Counter
import json

class ProjectStructureAnalyzer:
    """프로젝트 구조 분석 클래스"""
    
    def __init__(self, project_root=None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        
        # 제외할 디렉토리와 파일
        self.exclude_dirs = {
            'venv', '__pycache__', '.git', 'node_modules', 
            '.vscode', '.idea', 'dist', 'build'
        }
        self.exclude_files = {
            '.pyc', '.pyo', '.pyd', '.so', '.egg-info',
            '.DS_Store', 'Thumbs.db', '.gitkeep'
        }
        
        # 중요 파일들
        self.important_files = {
            'requirements.txt', 'README.md', 'LEARNING_NOTES.md',
            '.env', '.gitignore', 'finance_data.db'
        }
        
        # 파일 유형별 아이콘
        self.file_icons = {
            '.py': '🐍',
            '.db': '🗄️',
            '.sql': '📊',
            '.csv': '📄',
            '.json': '📋',
            '.md': '📖',
            '.txt': '📝',
            '.log': '📜',
            '.yml': '⚙️',
            '.yaml': '⚙️',
            '.env': '🔐',
            '.gitignore': '🚫'
        }
    
    def get_file_icon(self, file_path):
        """파일 확장자에 따른 아이콘 반환"""
        suffix = file_path.suffix.lower()
        return self.file_icons.get(suffix, '📄')
    
    def format_size(self, size_bytes):
        """파일 크기를 읽기 쉬운 형태로 변환"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def should_exclude(self, path):
        """파일/디렉토리를 제외할지 판단"""
        name = path.name
        
        # 제외할 디렉토리 체크
        if path.is_dir() and name in self.exclude_dirs:
            return True
            
        # 제외할 파일 확장자 체크
        if path.is_file() and any(name.endswith(ext) for ext in self.exclude_files):
            return True
            
        # 숨김 파일 체크 (단, 중요 파일은 포함)
        if name.startswith('.') and name not in self.important_files:
            return True
            
        return False
    
    def scan_directory(self, directory, max_depth=4, current_depth=0):
        """디렉토리를 재귀적으로 스캔하여 구조 정보 수집"""
        if current_depth >= max_depth:
            return []
        
        items = []
        try:
            # 디렉토리 내 항목들을 정렬하여 처리
            path_items = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            
            for item in path_items:
                if self.should_exclude(item):
                    continue
                
                relative_path = item.relative_to(self.project_root)
                
                if item.is_dir():
                    # 디렉토리 정보
                    subdirectories = self.scan_directory(item, max_depth, current_depth + 1)
                    items.append({
                        'type': 'directory',
                        'name': item.name,
                        'path': str(relative_path),
                        'full_path': str(item),
                        'children': subdirectories,
                        'depth': current_depth
                    })
                else:
                    # 파일 정보
                    try:
                        size = item.stat().st_size
                        modified = datetime.fromtimestamp(item.stat().st_mtime)
                    except (OSError, ValueError):
                        size = 0
                        modified = datetime.now()
                    
                    items.append({
                        'type': 'file',
                        'name': item.name,
                        'path': str(relative_path),
                        'full_path': str(item),
                        'size': size,
                        'modified': modified,
                        'extension': item.suffix.lower(),
                        'icon': self.get_file_icon(item),
                        'depth': current_depth,
                        'is_important': item.name in self.important_files
                    })
        except PermissionError:
            pass
        
        return items
    
    def print_tree_structure(self, items, prefix="", is_last=True):
        """트리 구조로 프로젝트 구조 출력 (CSV 파일 그룹화 기능 포함)"""
        
        # CSV 파일들을 별도로 그룹화
        csv_files = [item for item in items if item['type'] == 'file' and item['extension'] == '.csv']
        other_items = [item for item in items if not (item['type'] == 'file' and item['extension'] == '.csv')]
        
        # CSV 파일이 3개 이상인 경우 그룹화
        if len(csv_files) >= 3:
            # 크기별로 정렬 (큰 것부터)
            csv_files.sort(key=lambda x: x['size'], reverse=True)
            
            # 처음 2개만 표시하고 나머지는 요약
            display_items = other_items + csv_files[:2]
            remaining_csv = len(csv_files) - 2
            
            # 나머지 CSV 파일들의 총 크기 계산
            remaining_size = sum(csv['size'] for csv in csv_files[2:])
            
            # 요약 아이템 추가
            summary_item = {
                'type': 'csv_summary',
                'name': f"외 {remaining_csv}개 CSV 파일",
                'size': remaining_size,
                'icon': '📄'
            }
            display_items.append(summary_item)
        else:
            # CSV 파일이 적으면 모두 표시
            display_items = items
        
        for i, item in enumerate(display_items):
            is_last_item = (i == len(display_items) - 1)
            
            # 트리 연결선 생성
            if is_last_item:
                current_prefix = "└── "
                next_prefix = prefix + "    "
            else:
                current_prefix = "├── "
                next_prefix = prefix + "│   "
            
            if item['type'] == 'directory':
                print(f"{prefix}{current_prefix}📁 {item['name']}/")
                if item['children']:
                    self.print_tree_structure(item['children'], next_prefix, is_last_item)
            elif item['type'] == 'csv_summary':
                # CSV 요약 표시
                size_str = self.format_size(item['size'])
                print(f"{prefix}{current_prefix}{item['icon']} {item['name']} ({size_str})")
            else:
                # 일반 파일
                size_str = self.format_size(item['size'])
                importance = " ⭐" if item['is_important'] else ""
                print(f"{prefix}{current_prefix}{item['icon']} {item['name']} ({size_str}){importance}")
    
    def analyze_file_statistics(self, items):
        """파일 통계 분석"""
        stats = {
            'total_files': 0,
            'total_size': 0,
            'by_extension': Counter(),
            'python_files': [],
            'important_files': [],
            'large_files': [],
            'csv_files': []  # CSV 파일 별도 추적
        }
        
        def process_items(item_list):
            for item in item_list:
                if item['type'] == 'directory':
                    process_items(item['children'])
                else:
                    stats['total_files'] += 1
                    stats['total_size'] += item['size']
                    stats['by_extension'][item['extension']] += 1
                    
                    # Python 파일 수집
                    if item['extension'] == '.py':
                        stats['python_files'].append(item)
                    
                    # CSV 파일 수집
                    if item['extension'] == '.csv':
                        stats['csv_files'].append(item)
                    
                    # 중요 파일 수집
                    if item['is_important']:
                        stats['important_files'].append(item)
                    
                    # 큰 파일 수집 (1MB 이상)
                    if item['size'] > 1024 * 1024:
                        stats['large_files'].append(item)
        
        process_items(items)
        
        # 정렬
        stats['large_files'].sort(key=lambda x: x['size'], reverse=True)
        stats['csv_files'].sort(key=lambda x: x['size'], reverse=True)
        
        return stats
    
    def analyze_databases(self):
        """데이터베이스 파일 분석"""
        db_info = []
        
        for db_file in self.project_root.glob('**/*.db'):
            if self.should_exclude(db_file):
                continue
                
            try:
                size = db_file.stat().st_size
                modified = datetime.fromtimestamp(db_file.stat().st_mtime)
                
                # SQLite 데이터베이스 정보 추출
                tables = []
                try:
                    with sqlite3.connect(db_file) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        tables = [row[0] for row in cursor.fetchall()]
                except sqlite3.Error:
                    pass
                
                db_info.append({
                    'name': db_file.name,
                    'path': str(db_file.relative_to(self.project_root)),
                    'size': size,
                    'modified': modified,
                    'tables': tables
                })
            except (OSError, ValueError):
                pass
        
        return db_info
    
    def print_statistics(self, stats):
        """통계 정보 출력"""
        print("\n" + "="*60)
        print("📊 프로젝트 통계")
        print("="*60)
        
        print(f"📁 총 파일 수: {stats['total_files']:,}개")
        print(f"💾 총 파일 크기: {self.format_size(stats['total_size'])}")
        print(f"📅 분석 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 파일 유형별 통계
        print(f"\n📋 파일 유형별 통계:")
        for ext, count in stats['by_extension'].most_common(10):
            ext_display = ext if ext else "(확장자 없음)"
            icon = self.file_icons.get(ext, '📄')
            print(f"  {icon} {ext_display}: {count}개")
        
        # CSV 파일 요약 (3개 이상일 때만)
        if stats['csv_files'] and len(stats['csv_files']) >= 3:
            total_csv_size = sum(csv['size'] for csv in stats['csv_files'])
            print(f"\n📄 CSV 파일 요약 ({len(stats['csv_files'])}개):")
            print(f"  💾 총 크기: {self.format_size(total_csv_size)}")
            print(f"  📊 상위 파일들:")
            for csv_file in stats['csv_files'][:3]:  # 상위 3개만 표시
                size_str = self.format_size(csv_file['size'])
                print(f"    📄 {csv_file['name']} ({size_str})")
            if len(stats['csv_files']) > 3:
                remaining = len(stats['csv_files']) - 3
                remaining_size = sum(csv['size'] for csv in stats['csv_files'][3:])
                print(f"    📄 외 {remaining}개 파일 ({self.format_size(remaining_size)})")
        elif stats['csv_files']:
            print(f"\n📄 CSV 파일 ({len(stats['csv_files'])}개):")
            for csv_file in stats['csv_files']:
                size_str = self.format_size(csv_file['size'])
                print(f"  📄 {csv_file['path']} ({size_str})")
        
        # Python 파일 상세 정보
        if stats['python_files']:
            print(f"\n🐍 Python 파일 상세 ({len(stats['python_files'])}개):")
            for py_file in sorted(stats['python_files'], key=lambda x: x['path']):
                size_str = self.format_size(py_file['size'])
                print(f"  📄 {py_file['path']} ({size_str})")
        
        # 중요 파일 정보
        if stats['important_files']:
            print(f"\n⭐ 중요 파일 ({len(stats['important_files'])}개):")
            for important_file in stats['important_files']:
                size_str = self.format_size(important_file['size'])
                modified_str = important_file['modified'].strftime('%Y-%m-%d %H:%M')
                print(f"  {important_file['icon']} {important_file['name']} ({size_str}) - {modified_str}")
        
        # 큰 파일들
        if stats['large_files']:
            print(f"\n📦 큰 파일들 (1MB 이상, {len(stats['large_files'])}개):")
            for large_file in stats['large_files'][:5]:  # 상위 5개만
                size_str = self.format_size(large_file['size'])
                print(f"  {large_file['icon']} {large_file['path']} ({size_str})")
    
    def print_database_info(self, db_info):
        """데이터베이스 정보 출력"""
        if not db_info:
            print("\n🗄️ 데이터베이스 파일이 없습니다.")
            return
        
        print(f"\n🗄️ 데이터베이스 정보 ({len(db_info)}개):")
        print("-" * 40)
        
        for db in db_info:
            size_str = self.format_size(db['size'])
            modified_str = db['modified'].strftime('%Y-%m-%d %H:%M')
            
            print(f"\n📊 {db['name']}")
            print(f"   위치: {db['path']}")
            print(f"   크기: {size_str}")
            print(f"   수정: {modified_str}")
            
            if db['tables']:
                print(f"   테이블 ({len(db['tables'])}개): {', '.join(db['tables'])}")
            else:
                print("   테이블: 정보 없음")
    
    def save_report(self, items, stats, db_info):
        """분석 결과를 JSON 파일로 저장"""
        report = {
            'analysis_time': datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'statistics': {
                'total_files': stats['total_files'],
                'total_size': stats['total_size'],
                'file_extensions': dict(stats['by_extension']),
                'python_files_count': len(stats['python_files']),
                'csv_files_count': len(stats['csv_files']),
                'important_files_count': len(stats['important_files']),
                'large_files_count': len(stats['large_files'])
            },
            'databases': db_info,
            'structure': items
        }
        
        report_file = self.project_root / 'project_structure_report.json'
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n💾 상세 리포트 저장: {report_file}")
        except Exception as e:
            print(f"\n❌ 리포트 저장 실패: {e}")
    
    def run_analysis(self, save_report=False):
        """전체 분석 실행"""
        print("🔍 Finance Data Vibe 프로젝트 구조 분석")
        print("="*60)
        print(f"📍 분석 대상: {self.project_root}")
        print(f"🚫 제외 디렉토리: {', '.join(self.exclude_dirs)}")
        
        # 프로젝트 구조 스캔
        print("\n🌳 프로젝트 구조:")
        print("-" * 40)
        items = self.scan_directory(self.project_root)
        self.print_tree_structure(items)
        
        # 통계 분석
        stats = self.analyze_file_statistics(items)
        self.print_statistics(stats)
        
        # 데이터베이스 분석
        db_info = self.analyze_databases()
        self.print_database_info(db_info)
        
        # 리포트 저장 (옵션)
        if save_report:
            self.save_report(items, stats, db_info)
        
        print(f"\n✅ 프로젝트 구조 분석 완료!")

def main():
    """메인 실행 함수"""
    print("Finance Data Vibe 프로젝트 구조 분석기")
    print("=" * 50)
    
    # 프로젝트 루트 설정
    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1])
    else:
        project_root = Path.cwd()
    
    if not project_root.exists():
        print(f"❌ 디렉토리가 존재하지 않습니다: {project_root}")
        return
    
    # 분석기 실행
    analyzer = ProjectStructureAnalyzer(project_root)
    
    # 옵션 선택
    print("\n🎯 분석 옵션:")
    print("1. 기본 분석")
    print("2. 분석 + 리포트 저장")
    print("3. 종료")
    
    try:
        choice = input("\n선택 (1-3): ").strip()
        
        if choice == '1':
            analyzer.run_analysis(save_report=False)
        elif choice == '2':
            analyzer.run_analysis(save_report=True)
        elif choice == '3':
            print("👋 프로그램을 종료합니다.")
        else:
            print("❌ 잘못된 선택입니다.")
            
    except KeyboardInterrupt:
        print("\n\n👋 사용자가 프로그램을 중단했습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")

if __name__ == "__main__":
    main()