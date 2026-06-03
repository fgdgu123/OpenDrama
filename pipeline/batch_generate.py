"""
OpenDrama 批量生成器 — 多剧本队列处理

功能:
  - 自动扫描剧本目录，逐个生成
  - 每完成一部自动继续下一部
  - 错误跳过不中断，继续跑
  - 生成报告
"""
import sys, os, time, json, argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.generate import OpenDrama


def batch_generate(scripts_dir, output_dir, config=None, max_count=None, delay_between=5):
    """批量处理剧本目录"""
    d = Path(scripts_dir)
    if not d.exists():
        print(f"❌ 目录不存在: {scripts_dir}")
        return
    
    scripts = sorted(d.glob("*.md")) + sorted(d.glob("*.txt")) + sorted(d.glob("*.json"))
    if max_count:
        scripts = scripts[:max_count]
    
    print("=" * 55)
    print(f"  📚 OpenDrama 批量生成器")
    print(f"  剧本目录: {scripts_dir}")
    print(f"  找到: {len(scripts)} 个剧本")
    print(f"  配置: 风格={config.get('style','cinematic')} 锁脸={'✅' if config.get('ref_face') else '❌'}")
    print("=" * 55)
    
    results = []
    t_start = time.time()
    
    for i, script in enumerate(scripts):
        name = script.stem
        out = Path(output_dir) / f"{name}.mp4"
        
        print(f"\n── [{i+1}/{len(scripts)}] {name} ──")
        
        t0 = time.time()
        try:
            drama = OpenDrama(config)
            result = drama.run(str(script), str(out))
            dt = time.time() - t0
            
            ok = result and os.path.exists(str(out))
            results.append({
                "script": name,
                "output": str(out),
                "success": ok,
                "time": round(dt, 1),
                "size": os.path.getsize(str(out)) if ok and os.path.exists(str(out)) else 0
            })
            
            if ok:
                print(f"  ✅ {name} → {round(dt,1)}s")
            else:
                print(f"  ⚠️ {name}: 生成完成但文件不可用")
                
        except Exception as e:
            dt = time.time() - t0
            results.append({
                "script": name,
                "success": False,
                "error": str(e)[:200],
                "time": round(dt, 1)
            })
            print(f"  ❌ {name}: {e}")
        
        # Cool down between jobs
        if i < len(scripts) - 1:
            time.sleep(delay_between)
    
    total_time = time.time() - t_start
    
    # Report
    print(f"\n{'=' * 55}")
    print(f"  📊 批量生成报告")
    print(f"  耗时: {total_time:.0f}s ({total_time/60:.1f}分钟)")
    
    ok = sum(1 for r in results if r["success"])
    fail = len(results) - ok
    print(f"  成功: {ok} | 失败: {fail}")
    print(f"{'=' * 55}")
    
    for r in results:
        icon = "✅" if r["success"] else "❌"
        detail = f"{r.get('size',0)//1024}KB" if r.get("size") else r.get("error","")
        print(f"  {icon} {r['script']:40s} {r['time']}s {detail}")
    
    # Save report
    report_path = Path(output_dir) / f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "time": datetime.now().isoformat(),
            "total": len(results), "ok": ok, "fail": fail,
            "duration_s": total_time,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📄 报告已保存: {report_path}")
    
    return results


def main():
    p = argparse.ArgumentParser(description="OpenDrama 批量生成器")
    p.add_argument("--scripts-dir", default="my_scripts", help="剧本目录")
    p.add_argument("--output-dir", default="output/batch", help="输出目录")
    p.add_argument("--style", default="cinematic")
    p.add_argument("--ref-face", help="参考脸图")
    p.add_argument("--max", type=int, help="最多处理剧本数")
    p.add_argument("--delay", type=int, default=5, help="间隔秒数")
    
    # SSH
    p.add_argument("--ssh-host", default="connect.westc.seetacloud.com")
    p.add_argument("--ssh-port", type=int, default=38342)
    p.add_argument("--ssh-user", default="root")
    p.add_argument("--ssh-password", default="bBXvSvISTNNB")
    
    args = p.parse_args()
    
    config = {
        "output_dir": args.output_dir,
        "style": args.style,
        "ref_face": args.ref_face,
        "video_enabled": False,
        "subtitle_enabled": True,
        "tts_engine": "edge-tts",
        "tts_voice": "zh-CN-YunxiNeural",
        "ssh_host": args.ssh_host,
        "ssh_port": args.ssh_port,
        "ssh_user": args.ssh_user,
        "ssh_password": args.ssh_password,
        "width": 576, "height": 1024, "steps": 20,
        "ipadapter_weight": 0.8,
    }
    
    batch_generate(args.scripts_dir, args.output_dir, config, args.max, args.delay)


if __name__ == "__main__":
    main()
