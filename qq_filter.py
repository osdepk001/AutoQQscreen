#!/usr/bin/env python3
"""
QQ好友/群成员筛选工具
通过 NapCatQQ 的 HTTP API 获取好友和群成员信息，
按性别和年龄筛选后输出到文本文件。

用法:
    python qq_filter.py --sex male --age 20
    python qq_filter.py --sex female --min-age 18 --max-age 25
    python qq_filter.py --sex male --age 20 --output result.txt
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


class QQFilter:
    """QQ好友/群成员筛选器"""

    def __init__(self, api_url="http://127.0.0.1:8099/", token=None, timeout=30):
        self.api_url = api_url.rstrip("/") + "/"
        self.token = token
        self.timeout = timeout
        self.results = []  # [(qq, nickname, source, sex, age), ...]

    def _api_call(self, action, params=None):
        """调用 OneBot HTTP API"""
        url = self.api_url + action
        data = json.dumps(params or {}).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            print(f"[错误] 无法连接到 rbt API: {e}")
            print("请确保 rbt 已启动且 QQ 已登录")
            sys.exit(1)
        except Exception as e:
            print(f"[错误] API 调用失败 ({action}): {e}")
            return None

        if result.get("status") == "ok":
            return result.get("data")
        elif result.get("status") == "failed":
            print(f"[警告] API 返回失败 ({action}): {result.get('msg', '未知错误')}")
            return None
        else:
            # 有些实现直接返回 data
            return result

    def get_friends(self):
        """获取所有好友并查询详细信息"""
        print("[1/3] 正在获取好友列表...")
        friend_list = self._api_call("get_friend_list")
        if not friend_list:
            print("  好友列表为空或获取失败")
            return

        print(f"  获取到 {len(friend_list)} 个好友，正在查询详细信息...")
        for i, friend in enumerate(friend_list):
            user_id = friend.get("user_id")
            nickname = friend.get("nickname", "")
            remark = friend.get("remark", "")

            # 获取陌生人信息（包含性别年龄）
            info = self._api_call("get_stranger_info", {"user_id": user_id})
            if info:
                sex = info.get("sex", "unknown")
                age = info.get("age", 0)
                display_name = remark or nickname
                self.results.append((user_id, display_name, "好友", sex, age))

            # 进度显示
            if (i + 1) % 20 == 0:
                print(f"  进度: {i + 1}/{len(friend_list)}")
            time.sleep(0.3)  # 避免请求过快

        print(f"  好友查询完成，共 {len(friend_list)} 人")

    def get_group_members(self):
        """获取所有群及其成员"""
        print("[2/3] 正在获取群列表...")
        group_list = self._api_call("get_group_list")
        if not group_list:
            print("  群列表为空或获取失败")
            return

        print(f"  获取到 {len(group_list)} 个群，正在遍历群成员...")
        total_members = 0

        for g_idx, group in enumerate(group_list):
            group_id = group.get("group_id")
            group_name = group.get("group_name", str(group_id))

            member_list = self._api_call("get_group_member_list", {"group_id": group_id})
            if not member_list:
                continue

            print(f"  群进度: {g_idx + 1}/{len(group_list)} - {group_name} ({len(member_list)}人)，正在查询详细信息...")
            for member in member_list:
                user_id = member.get("user_id")
                nickname = member.get("nickname", "")
                card = member.get("card", "")
                
                # 调用 get_stranger_info 获取真实性别和年龄
                info = self._api_call("get_stranger_info", {"user_id": user_id})
                if info:
                    sex = info.get("sex", "unknown")
                    age = info.get("age", 0)
                else:
                    sex = member.get("sex", "unknown")
                    age = member.get("age", 0)

                display_name = card or nickname
                source = f"群[{group_name}]"
                self.results.append((user_id, display_name, source, sex, age))
                total_members += 1

        print(f"  群成员查询完成，共 {total_members} 人")

    def filter_results(self, sex=None, age=None, min_age=None, max_age=None):
        """按条件筛选结果"""
        sex_map = {
            "male": "male",
            "female": "female",
            "男": "male",
            "女": "female",
            "未知": "unknown",
            "unknown": "unknown",
        }

        filtered = []
        for qq, name, source, s, a in self.results:
            # 性别筛选
            if sex is not None:
                target_sex = sex_map.get(sex, sex)
                if s != target_sex:
                    continue

            # 年龄筛选
            if age is not None and a != age:
                continue
            if min_age is not None and a < min_age:
                continue
            if max_age is not None and a > max_age:
                continue

            filtered.append((qq, name, source, s, a))

        return filtered

    def export_to_file(self, filtered, output_path):
        """导出结果到文件"""
        sex_label = {"male": "男", "female": "女", "unknown": "未知"}

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"{'QQ号':<15} {'昵称':<20} {'来源':<25} {'性别':<6} {'年龄':<6}\n")
            f.write("-" * 80 + "\n")

            for qq, name, source, sex, age in filtered:
                sex_cn = sex_label.get(sex, sex)
                f.write(f"{qq:<15} {name:<20} {source:<25} {sex_cn:<6} {age}岁\n")

            f.write("-" * 80 + "\n")
            f.write(f"共筛选出 {len(filtered)} 人\n")

        print(f"\n[完成] 结果已导出到: {output_path}")
        print(f"共筛选出 {len(filtered)} 人")

    def print_results(self, filtered):
        """打印结果到控制台"""
        sex_label = {"male": "男", "female": "女", "unknown": "未知"}

        print(f"\n{'='*70}")
        print(f"{'QQ号':<15} {'昵称':<20} {'来源':<25} {'性别':<6} 年龄")
        print(f"{'-'*70}")

        for qq, name, source, sex, age in filtered:
            sex_cn = sex_label.get(sex, sex)
            print(f"{qq:<15} {name:<20} {source:<25} {sex_cn:<6} {age}岁")

        print(f"{'-'*70}")
        print(f"共筛选出 {len(filtered)} 人")


def main():
    parser = argparse.ArgumentParser(
        description="QQ好友/群成员筛选工具 - 按性别和年龄筛选",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python qq_filter.py --sex male --age 20
  python qq_filter.py --sex 男 --min-age 18 --max-age 25
  python qq_filter.py --sex female --age 20 --output result.txt
  python qq_filter.py --sex male --age 20 --api http://127.0.0.1:8099/api/
        """,
    )

    parser.add_argument("--sex", type=str, default=None,
                        help="性别筛选: male/男, female/女, unknown/未知")
    parser.add_argument("--age", type=int, default=None,
                        help="精确年龄筛选")
    parser.add_argument("--min-age", type=int, default=None,
                        help="最小年龄")
    parser.add_argument("--max-age", type=int, default=None,
                        help="最大年龄")
    parser.add_argument("--output", "-o", type=str, default="qq_filter_result.txt",
                        help="输出文件路径 (默认: qq_filter_result.txt)")
    parser.add_argument("--api", type=str, default="http://127.0.0.1:8099/",
                        help="rbt OneBot HTTP API 地址 (默认: http://127.0.0.1:8099/)")
    parser.add_argument("--token", type=str, default=None,
                        help="API 访问令牌 (如果配置了的话)")
    parser.add_argument("--no-friends", action="store_true",
                        help="不查询好友列表")
    parser.add_argument("--no-groups", action="store_true",
                        help="不查询群成员列表")

    args = parser.parse_args()

    # 验证参数
    if args.sex is None and args.age is None and args.min_age is None and args.max_age is None:
        print("[错误] 请至少指定一个筛选条件: --sex, --age, --min-age, --max-age")
        parser.print_help()
        sys.exit(1)

    if args.sex:
        valid_sex = ["male", "female", "unknown", "男", "女", "未知"]
        if args.sex not in valid_sex:
            print(f"[错误] 无效的性别参数: {args.sex}")
            print(f"可选值: {', '.join(valid_sex)}")
            sys.exit(1)

    # 创建筛选器
    qf = QQFilter(api_url=args.api, token=args.token)

    print("=" * 50)
    print("  QQ 好友/群成员筛选工具")
    print("=" * 50)
    print(f"  API 地址: {args.api}")
    if args.sex:
        print(f"  性别筛选: {args.sex}")
    if args.age is not None:
        print(f"  年龄筛选: {args.age}岁")
    if args.min_age is not None:
        print(f"  最小年龄: {args.min_age}岁")
    if args.max_age is not None:
        print(f"  最大年龄: {args.max_age}岁")
    print()

    # 获取数据
    if not args.no_friends:
        qf.get_friends()
    else:
        print("[跳过] 好友列表查询")

    if not args.no_groups:
        qf.get_group_members()
    else:
        print("[跳过] 群成员查询")

    print(f"\n[3/3] 正在筛选... (共 {len(qf.results)} 条记录)")

    # 筛选
    filtered = qf.filter_results(
        sex=args.sex,
        age=args.age,
        min_age=args.min_age,
        max_age=args.max_age,
    )

    # 输出
    output_path = Path(args.output)
    qf.export_to_file(filtered, output_path)

    # 同时打印到控制台
    qf.print_results(filtered)


if __name__ == "__main__":
    main()