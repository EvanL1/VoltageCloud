#!/usr/bin/env python3
"""
本地运行设备模拟器，跳过 Docker 问题
"""
import subprocess
import sys
import os

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import AWSIoTPythonSDK
        print("✅ AWSIoTPythonSDK 已安装")
        return True
    except ImportError:
        print("❌ 需要安装 AWSIoTPythonSDK")
        print("正在安装...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "AWSIoTPythonSDK"])
            print("✅ AWSIoTPythonSDK 安装完成")
            return True
        except subprocess.CalledProcessError:
            print("❌ 安装失败")
            return False

def run_simulator_and_monitor():
    """同时运行设备模拟器和监控脚本"""
    print("🚀 启动完整的 IoT 数据流测试")
    print("=" * 60)
    
    # 检查证书文件
    if not os.path.exists("certificates/test-device-001-config.json"):
        print("❌ 找不到设备配置文件，请先运行 create_test_device.py")
        return False
        
    # 检查依赖
    if not check_dependencies():
        return False
    
    print("\n📡 准备启动设备模拟器...")
    print("⏱️  将运行 10 分钟，每 5 秒发送一次数据")
    print("\n🔍 同时会监控数据流...")
    
    input("按 Enter 键开始...")
    
    try:
        # 在后台运行设备模拟器
        print("\n🔄 启动设备模拟器...")
        simulator_process = subprocess.Popen([
            sys.executable, "iot_device_simulator.py", "600", "5"
        ])
        
        print("📊 等待 10 秒让设备连接...")
        import time
        time.sleep(10)
        
        # 运行监控脚本
        print("🔍 启动监控...")
        monitor_process = subprocess.Popen([
            sys.executable, "monitor_data_flow.py"
        ])
        
        # 等待两个进程完成
        print("⏳ 等待进程完成...")
        simulator_process.wait()
        monitor_process.terminate()
        
        print("\n✅ 测试完成!")
        
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
        if 'simulator_process' in locals():
            simulator_process.terminate()
        if 'monitor_process' in locals():
            monitor_process.terminate()
    except Exception as e:
        print(f"❌ 运行过程中出错: {str(e)}")
        
    return True

if __name__ == "__main__":
    run_simulator_and_monitor()