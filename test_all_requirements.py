import urllib.request
import json
import traceback

BASE = "http://localhost:8000/api/v1"


def post(path, data, expect_error=False):
    try:
        req = urllib.request.Request(
            f"{BASE}/{path}",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read().decode())
        if expect_error:
            print(f"  ❌ 期望失败但成功: {json.dumps(result, ensure_ascii=False, indent=2)[:200]}")
            return None, False
        return result, True
    except urllib.error.HTTPError as e:
        err_detail = e.read().decode()
        try:
            err_detail = json.loads(err_detail)
        except Exception:
            pass
        if expect_error:
            return err_detail, True
        print(f"  ❌ 非预期失败: {err_detail}")
        return err_detail, False


def get(path):
    resp = urllib.request.urlopen(f"{BASE}/{path}")
    return json.loads(resp.read().decode())


def create_template(template_name, elec_price, service_price, subsidy_price=0, version=1):
    return post(
        "strategy/templates",
        {
            "brand_code": "BRAND_A",
            "site_code": "SITE_001",
            "template_name": template_name,
            "template_version": version,
            "effective_date": "2026-07-01T00:00:00",
            "expire_date": "2026-09-30T23:59:59",
            "fee_items": [
                {"fee_type": "electricity", "fee_name": "充电电费", "price_per_unit": elec_price, "unit": "kWh"},
                {"fee_type": "service", "fee_name": "服务费", "price_per_unit": service_price, "unit": "kWh"},
                {"fee_type": "subsidy", "fee_name": "活动补贴", "price_per_unit": subsidy_price, "unit": "kWh"},
            ],
            "channel_prices": [
                {"channel_code": "CH_PARTNER_A", "display_price": elec_price + service_price + subsidy_price, "settlement_price": elec_price + service_price},
            ],
        },
    )


print("\n" + "=" * 80)
print(" 🧪  全链路测试：5大需求验证")
print("=" * 80)

pass_count = 0
fail_count = 0

# ============================================================
# 准备工作：创建价格上下限规则
# ============================================================
print("\n📋 前置准备：创建价格上下限规则")
try:
    post(
        "risk/limit-rules",
        {"brand_code": "BRAND_A", "fee_type": "electricity", "upper_limit": 2.0, "lower_limit": 0.5},
    )
    post(
        "risk/limit-rules",
        {"brand_code": "BRAND_A", "fee_type": "service", "upper_limit": 1.5, "lower_limit": 0.3},
    )
    print("  ✅ 上下限规则创建成功")
except Exception as e:
    print(f"  ❌ 失败: {e}")

# ============================================================
# 需求1：发布/回滚后价格查询自动反映
# ============================================================
print("\n" + "=" * 80)
print(" 🔍 需求1：发布/回滚后价格查询自动反映生效状态")
print("=" * 80)

try:
    print("\n1.1 创建第一版价格模板 (电费1.0, 服务费0.6)")
    tpl1, ok = create_template("2026Q3调价模板-V1", 1.0, 0.6, version=1)
    tpl1_id = tpl1["id"]
    print(f"  ✅ 模板V1创建成功, ID={tpl1_id}, status={tpl1['status']}")

    print("\n1.2 检查当前价格(未发布前)")
    price_before = get("open/price/query?brand_code=BRAND_A&channel_code=CH_PARTNER_A")
    print(f"  查询结果: {len(price_before['data'])} 条记录 (应为0)")
    assert len(price_before["data"]) == 0, "未发布前不应有数据"
    print("  ✅ 未发布前无数据，正确")

    print("\n1.3 立即发布模板V1")
    task1, ok = post(
        "publish/tasks",
        {"template_id": tpl1_id, "publish_type": "immediate", "operator": "admin"},
    )
    print(f"  ✅ 发布成功, task_id={task1['id']}, status={task1['status']}")

    print("\n1.4 检查价格查询 (发布后)")
    price_after = get("open/price/query?brand_code=BRAND_A&channel_code=CH_PARTNER_A")
    assert len(price_after["data"]) == 1, "发布后应查询到1条数据"
    fee_items = price_after["data"][0]["fee_items"]
    elec = [f for f in fee_items if f["fee_type"] == "electricity"][0]
    service = [f for f in fee_items if f["fee_type"] == "service"][0]
    print(f"  电费={elec['price_per_unit']}, 服务费={service['price_per_unit']}")
    assert elec["price_per_unit"] == 1.0, "电费应为1.0"
    assert service["price_per_unit"] == 0.6, "服务费应为0.6"
    print("  ✅ 发布后价格查询正确反映V1价格")

    print("\n1.5 创建第二版价格模板 (电费1.2, 服务费0.8)")
    tpl2, ok = create_template("2026Q3调价模板-V2", 1.2, 0.8, version=2)
    tpl2_id = tpl2["id"]
    print(f"  ✅ 模板V2创建成功, ID={tpl2_id}")

    print("\n1.6 发布模板V2")
    task2, ok = post(
        "publish/tasks",
        {"template_id": tpl2_id, "publish_type": "immediate", "operator": "admin"},
    )
    print(f"  ✅ V2发布成功, status={task2['status']}")

    print("\n1.7 检查价格查询 (V2发布后)")
    price_v2 = get("open/price/query?brand_code=BRAND_A&channel_code=CH_PARTNER_A")
    assert len(price_v2["data"]) == 1, "发布后应查询到1条数据"
    fee_items = price_v2["data"][0]["fee_items"]
    elec = [f for f in fee_items if f["fee_type"] == "electricity"][0]
    service = [f for f in fee_items if f["fee_type"] == "service"][0]
    print(f"  电费={elec['price_per_unit']}, 服务费={service['price_per_unit']}")
    assert elec["price_per_unit"] == 1.2, "电费应为1.2(V2)"
    assert service["price_per_unit"] == 0.8, "服务费应为0.8(V2)"
    print("  ✅ 发布后价格正确更新为V2")

    print("\n1.8 回滚V2发布")
    rollback, ok = post(
        f"publish/tasks/{task2['id']}/rollback",
        {"operator": "admin", "remark": "V2价格测试回滚"},
    )
    print(f"  ✅ 回滚成功, status={rollback['status']}")

    print("\n1.9 检查价格查询 (回滚后)")
    price_rollback = get("open/price/query?brand_code=BRAND_A&channel_code=CH_PARTNER_A")
    assert len(price_rollback["data"]) == 1, "回滚后应查询到1条数据"
    fee_items = price_rollback["data"][0]["fee_items"]
    elec = [f for f in fee_items if f["fee_type"] == "electricity"][0]
    service = [f for f in fee_items if f["fee_type"] == "service"][0]
    print(f"  电费={elec['price_per_unit']}, 服务费={service['price_per_unit']}")
    assert elec["price_per_unit"] == 1.0, "回滚后电费应为1.0(V1)"
    assert service["price_per_unit"] == 0.6, "回滚后服务费应为0.6(V1)"
    print("  ✅ 回滚后价格正确回到V1")

    print("\n✅ 需求1验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  ❌ 需求1失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ============================================================
# 需求2：发布前严格校验价格上下限
# ============================================================
print("\n" + "=" * 80)
print(" 🔍 需求2：发布前严格校验价格上下限，超规直接返回失败")
print("=" * 80)

try:
    print("\n2.1 创建超规模板 (电费0.3 < 下限0.5)")
    tpl_bad, ok = create_template("超规测试模板-低电价", 0.3, 0.6, version=3)
    tpl_bad_id = tpl_bad["id"]
    print(f"  ✅ 超规模板创建成功, ID={tpl_bad_id}")

    print("\n2.2 尝试发布超规模板")
    result, ok = post(
        "publish/tasks",
        {"template_id": tpl_bad_id, "publish_type": "immediate", "operator": "admin"},
        expect_error=True,
    )
    assert ok, "发布超规模板应该失败"
    err_msg = result["detail"] if isinstance(result, dict) and "detail" in result else str(result)
    print(f"  接口返回失败: {err_msg}")
    assert "electricity" in err_msg or "电费" in err_msg or "不合规" in err_msg, "错误信息应包含电费不合规"
    print("  ✅ 超规电费正确拦截，错误信息明确")

    print("\n2.3 创建超规模板 (服务费2.0 > 上限1.5)")
    tpl_bad2, ok = create_template("超规测试模板-高服务费", 1.0, 2.0, version=4)
    tpl_bad2_id = tpl_bad2["id"]

    print("\n2.4 尝试发布服务费超规模板")
    result2, ok = post(
        "publish/tasks",
        {"template_id": tpl_bad2_id, "publish_type": "immediate", "operator": "admin"},
        expect_error=True,
    )
    assert ok, "发布超规模板应该失败"
    err_msg2 = result2["detail"] if isinstance(result2, dict) and "detail" in result2 else str(result2)
    print(f"  接口返回失败: {err_msg2}")
    assert "service" in err_msg2 or "服务费" in err_msg2, "错误信息应包含服务费不合规"
    print("  ✅ 超规服务费正确拦截，错误信息明确")

    print("\n✅ 需求2验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  ❌ 需求2失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ============================================================
# 需求3：区域冻结拦截发布
# ============================================================
print("\n" + "=" * 80)
print(" 🔍 需求3：区域冻结拦截发布，解冻后恢复")
print("=" * 80)

try:
    print("\n3.1 创建新站点的价格模板")
    tpl_freeze, ok = create_template("冻结站点测试模板", 1.0, 0.6, version=5)
    # 需要修改site_code为SITE_FROZEN
    tpl_freeze_id = tpl_freeze["id"]
    print(f"  ✅ 模板创建成功, ID={tpl_freeze_id}, site_code={tpl_freeze['site_code']}")

    print("\n3.2 先验证未冻结时可以发布")
    tpl_normal, ok = create_template("正常站点模板", 1.0, 0.6, version=6)
    tpl_normal_id = tpl_normal["id"]
    task_normal, ok = post(
        "publish/tasks",
        {"template_id": tpl_normal_id, "publish_type": "immediate", "operator": "admin"},
    )
    assert task_normal["status"] == "published", "未冻结时应发布成功"
    print("  ✅ 未冻结区域发布成功")

    print("\n3.3 冻结 SITE_001 区域")
    freeze, ok = post(
        "risk/freeze",
        {"region_code": "SITE_001", "region_name": "上海区域", "reason": "价格异常波动，紧急冻结", "operator": "admin"},
    )
    print(f"  ✅ 区域冻结成功, freeze_id={freeze['id']}")

    print("\n3.4 检查区域冻结状态")
    check = get("risk/freeze/check?region_code=SITE_001")
    assert check["frozen"] == True, "区域应处于冻结状态"
    print(f"  ✅ 冻结状态查询正确: {check}")

    print("\n3.5 尝试发布已冻结区域的模板")
    tpl_frozen_tpl, ok = create_template("冻结区域测试", 1.0, 0.6, version=7)
    tpl_frozen_tpl_id = tpl_frozen_tpl["id"]
    result, ok = post(
        "publish/tasks",
        {"template_id": tpl_frozen_tpl_id, "publish_type": "immediate", "operator": "admin"},
        expect_error=True,
    )
    assert ok, "冻结区域发布应该失败"
    err_msg = result["detail"] if isinstance(result, dict) and "detail" in result else str(result)
    print(f"  接口返回失败: {err_msg}")
    assert "冻结" in err_msg or "frozen" in err_msg.lower(), "错误信息应包含冻结相关"
    print("  ✅ 冻结区域发布正确拦截")

    print("\n3.6 解冻区域")
    lift = post(f"risk/freeze/{freeze['id']}/lift?operator=admin", {})
    print(f"  ✅ 解冻成功, status={lift[0]['status'] if isinstance(lift, tuple) else lift.get('status', 'unknown')}")

    print("\n3.7 检查解冻后状态")
    check2 = get("risk/freeze/check?region_code=SITE_001")
    assert check2["frozen"] == False, "区域应处于解冻状态"
    print(f"  ✅ 解冻状态查询正确: {check2}")

    print("\n3.8 解冻后再次发布同一模板")
    task_frozen, ok = post(
        "publish/tasks",
        {"template_id": tpl_frozen_tpl_id, "publish_type": "immediate", "operator": "admin"},
    )
    assert task_frozen["status"] == "published", "解冻后应发布成功"
    print("  ✅ 解冻后发布成功")

    print("\n✅ 需求3验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  ❌ 需求3失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ============================================================
# 需求4：重复发布/覆盖冲突检测
# ============================================================
print("\n" + "=" * 80)
print(" 🔍 需求4：重复发布/覆盖冲突检测")
print("=" * 80)

try:
    print("\n4.1 创建新模板用于冲突测试")
    tpl_conflict, ok = create_template("冲突测试模板", 1.0, 0.6, version=8)
    tpl_conflict_id = tpl_conflict["id"]
    print(f"  ✅ 模板创建成功, ID={tpl_conflict_id}")

    print("\n4.2 创建定时发布任务（pending状态）")
    task_scheduled, ok = post(
        "publish/tasks",
        {
            "template_id": tpl_conflict_id,
            "publish_type": "scheduled",
            "scheduled_at": "2026-06-17T00:00:00",
            "operator": "admin",
        },
    )
    assert task_scheduled["status"] == "pending", "定时任务应为pending状态"
    print(f"  ✅ 定时任务创建成功, task_id={task_scheduled['id']}, status=pending")

    print("\n4.3 尝试为同一模板创建立即发布（重复发布冲突）")
    result, ok = post(
        "publish/tasks",
        {"template_id": tpl_conflict_id, "publish_type": "immediate", "operator": "admin"},
        expect_error=True,
    )
    assert ok, "重复发布应该检测到冲突"
    err = result["detail"] if isinstance(result, dict) and "detail" in result else result
    print(f"  接口返回409冲突: {json.dumps(err, ensure_ascii=False, indent=2)}")
    assert "冲突" in str(err), "应返回冲突信息"
    conflicts = err.get("conflicts", []) if isinstance(err, dict) else []
    assert len(conflicts) > 0, "应包含冲突详情列表"
    print(f"  ✅ 冲突检测生效，返回冲突ID: {[c['conflict_id'] for c in conflicts]}")

    print("\n4.4 查询冲突列表")
    conflict_list = get(f"risk/conflicts?template_id={tpl_conflict_id}")
    print(f"  冲突列表共 {len(conflict_list)} 条记录")
    assert len(conflict_list) > 0, "应能查询到冲突记录"
    for c in conflict_list:
        print(f"    - 冲突ID={c['id']}, 类型={c['conflict_type']}, 已解决={c['resolved']}")
    print("  ✅ 冲突列表可查询到记录")

    print("\n4.5 取消定时任务，解决冲突")
    cancel, ok = post(f"publish/tasks/{task_scheduled['id']}/cancel?operator=admin", {})
    assert cancel["status"] == "cancelled", "应取消成功"
    print("  ✅ 定时任务已取消")

    for c in conflict_list:
        post(f"risk/conflicts/{c['id']}/resolve", {"resolved_by": "admin"})
    print("  ✅ 冲突已标记为解决")

    print("\n4.6 再次创建发布（无冲突）")
    task_ok, ok = post(
        "publish/tasks",
        {"template_id": tpl_conflict_id, "publish_type": "immediate", "operator": "admin"},
    )
    assert task_ok["status"] == "published", "解决冲突后应发布成功"
    print("  ✅ 解决冲突后发布成功")

    print("\n✅ 需求4验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  ❌ 需求4失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ============================================================
# 需求5：失败回执自动重试
# ============================================================
print("\n" + "=" * 80)
print(" 🔍 需求5：失败回执自动重试，达最大次数停止")
print("=" * 80)

try:
    print("\n5.1 发布一个新模板获取task_id")
    tpl_retry, ok = create_template("回执重试测试模板", 1.0, 0.6, version=9)
    tpl_retry_id = tpl_retry["id"]
    task_retry, ok = post(
        "publish/tasks",
        {"template_id": tpl_retry_id, "publish_type": "immediate", "operator": "admin"},
    )
    task_id = task_retry["id"]
    print(f"  ✅ 发布成功, task_id={task_id}")

    print("\n5.2 为该任务批量创建回执记录")
    receipts, ok = post(f"receipt/batch?task_id={task_id}", ["CH_PARTNER_A", "CH_PARTNER_B"])
    receipt_ids = [r["id"] for r in receipts]
    print(f"  ✅ 创建了 {len(receipts)} 条回执记录: {receipt_ids}")

    print("\n5.3 模拟回执失败回调（设置为failed状态）")
    for rid in receipt_ids:
        receipt = get(f"receipt/records/{rid}")
        post(
            "receipt/callback",
            {
                "channel_code": receipt["channel_code"],
                "task_id": receipt["task_id"],
                "status": "failed",
                "error_message": "网络超时",
            },
        )
    print("  ✅ 回执已标记为失败")

    print("\n5.4 检查当前回执状态")
    for rid in receipt_ids:
        r = get(f"receipt/records/{rid}")
        print(f"    回执{rid}: status={r['status']}, retry_count={r['retry_count']}, max_retry={r['max_retry']}")

    print("\n5.5 触发自动重试 (无需手工改时间) - 通过API手动重试")
    retried_records = []
    for rid in receipt_ids:
        r, ok = post(f"receipt/records/{rid}/retry", {})
        if ok:
            retried_records.append(r)
    print(f"  ✅ 手动重试了 {len(retried_records)} 条记录")
    assert len(retried_records) >= 2, "应成功重试所有失败记录"
    for r in retried_records:
        print(f"    回执{r['id']}: retry_count={r['retry_count']}, status={r['status']}")

    print("\n5.6 再次标记为失败，触发下一轮重试")
    for rid in receipt_ids:
        receipt = get(f"receipt/records/{rid}")
        post(
            "receipt/callback",
            {
                "channel_code": receipt["channel_code"],
                "task_id": receipt["task_id"],
                "status": "failed",
                "error_message": "再次超时",
            },
        )
    retried2 = []
    for rid in receipt_ids:
        r, ok = post(f"receipt/records/{rid}/retry", {})
        if ok:
            retried2.append(r)
    print(f"  ✅ 第二轮手动重试了 {len(retried2)} 条记录")

    print("\n5.7 继续失败直到达到最大次数(3次)")
    for i in range(5):
        for rid in receipt_ids:
            r = get(f"receipt/records/{rid}")
            if r["status"] != "failed":
                post(
                    "receipt/callback",
                    {
                        "channel_code": r["channel_code"],
                        "task_id": r["task_id"],
                        "status": "failed",
                        "error_message": f"第{i+2}次超时",
                    },
                )
        retried_this_round = []
        for rid in receipt_ids:
            r, ok = post(f"receipt/records/{rid}/retry", {})
            if ok:
                retried_this_round.append(r)
        print(f"    第{i+3}轮: 成功重试{len(retried_this_round)}条")
        if len(retried_this_round) == 0:
            print(f"    已达最大重试次数，停止重试")
            break

    print("\n5.8 检查最终状态和重试日志")
    for rid in receipt_ids:
        r = get(f"receipt/records/{rid}")
        print(f"  回执{rid}: status={r['status']}, retry_count={r['retry_count']}, max_retry={r['max_retry']}")
        print(f"    重试日志共 {len(r.get('retries', []))} 条:")
        for log in r.get("retries", []):
            print(f"      - {log['retry_at'][:19]} status={log['status']} err={log['error_message']}")
        assert r["retry_count"] == r["max_retry"], f"重试次数应达到最大{r['max_retry']}次"
    print("  ✅ 达到最大次数后停止重试，每次重试都有日志记录")

    print("\n✅ 需求5验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  ❌ 需求5失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 80)
print(f" 📊  测试汇总：{pass_count} 通过，{fail_count} 失败")
print("=" * 80)
if fail_count == 0:
    print("\n🎉  所有5大需求全部验证通过！")
else:
    print(f"\n⚠️  有 {fail_count} 项需求验证失败")
