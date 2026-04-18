import os
from loguru import logger

SERVICE_TEMPLATE = """[Unit]
Description=R-MAN: Universal AI Agent Service
After=network.target

[Service]
# 自动生成的运行路径
WorkingDirectory={work_dir}
Environment=PYTHONPATH=.
Environment=PYTHONUNBUFFERED=1

# 执行路径指向项目本地 venv
ExecStart={python_path} rman/main.py

# 自动重启策略
Restart=always
RestartSec=5

# 日志重定向
StandardOutput=append:{work_dir}/logs/stdout.log
StandardError=append:{work_dir}/logs/stderr.log

[Install]
WantedBy=multi-user.target
"""

def generate_service_file():
    """根据当前绝对路径生成 rman.service"""
    try:
        work_dir = os.getcwd()
        python_path = os.path.join(work_dir, "venv/bin/python")
        
        if not os.path.exists(python_path):
            logger.error("Virtual environment (venv) not found. Please run setup.sh first.")
            return False

        content = SERVICE_TEMPLATE.format(
            work_dir=work_dir,
            python_path=python_path
        )

        with open("rman.service", "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"✅ 已成功生成 systemd 配置文件: {os.path.join(work_dir, 'rman.service')}")
        return True
    except Exception as e:
        logger.error(f"Failed to generate service file: {e}")
        return False

if __name__ == "__main__":
    generate_service_file()
