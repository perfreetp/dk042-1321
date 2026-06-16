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
            print(f"  X 期望失败但成功: {json.dumps(result, ensure_ascii=False, indent=2)[:200]}")
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
        print(f"  X 非预期失败: {err_detail}")
        return err_detail, False


def get(path):
    resp = urllib.request.urlopen(f"{BASE}/{path}")
    return json.loads(resp.read().decode())


def create_template(template_name, elec_price, service_price, subsidy_price=0, version=1,
                    brand_code="BRAND_A", site_code="SITE_001"):
    return post(
        "strategy/templates",
        {
            "brand_code": brand_code,
            "site_code": site_code,
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
                {"channel_code": "CH_A", "display_price": elec_price + service_price, "settlement_price": elec_price, "discount_rate": 1.0},
            ],
        },
    )


pass_count = 0
fail_count = 0

print("=" * 80)
print("  全链路测试：4大新需求验证")
print("=" * 80)

print("\n  前置准备：创建价格上下限规则")
post("risk/limit-rules", {
    "brand_code": "BRAND_A",
    "fee_type": "electricity",
    "upper_limit": 3.0,
    "lower_limit": 0.5,
    "enabled": True,
})
post("risk/limit-rules", {
    "brand_code": "BRAND_A",
    "fee_type": "service",
    "upper_limit": 2.0,
    "lower_limit": 0.1,
    "enabled": True,
})
print("  OK 上下限规则创建成功")

# ======================================================================
#  需求1：模板版本明确区分，回滚按发布时间回到真正上一版
# ======================================================================
print("\n" + "=" * 80)
print("  需求1：模板版本明确区分，回滚按发布时间回到真正上一版")
print("=" * 80)

try:
    print("\n1.1 创建V1模板 (电费1.0, 服务费0.6)")
    v1, ok = create_template("模板A-V1", 1.0, 0.6, version=1)
    assert ok, f"V1创建失败: {v1}"
    v1_id = v1["id"]
    print(f"  OK V1创建成功, id={v1_id}, status={v1['status']}")

    print("\n1.2 发布V1")
    t1, ok = post("publish/tasks", {
        "template_id": v1_id,
        "publish_type": "immediate",
        "operator": "admin",
    })
    assert ok, f"V1发布失败: {t1}"
    print(f"  OK V1发布成功, task_id={t1['id']}, status={t1['status']}")

    print("\n1.3 创建V2模板 (电费1.2, 服务费0.8), 版本号也是1 (模拟不同模板同版本号)")
    v2, ok = create_template("模板A-V2", 1.2, 0.8, version=1)
    assert ok, f"V2创建失败: {v2}"
    v2_id = v2["id"]
    print(f"  OK V2创建成功, id={v2_id}")

    print("\n1.4 发布V2")
    t2, ok = post("publish/tasks", {
        "template_id": v2_id,
        "publish_type": "immediate",
        "operator": "admin",
    })
    assert ok, f"V2发布失败: {t2}"
    print(f"  OK V2发布成功, task_id={t2['id']}, status={t2['status']}")

    print("\n1.5 创建V3模板 (电费1.5, 服务费1.0)")
    v3, ok = create_template("模板A-V3", 1.5, 1.0, version=2)
    assert ok, f"V3创建失败: {v3}"
    v3_id = v3["id"]

    print("\n1.6 发布V3")
    t3, ok = post("publish/tasks", {
        "template_id": v3_id,
        "publish_type": "immediate",
        "operator": "admin",
    })
    assert ok, f"V3发布失败: {t3}"
    print(f"  OK V3发布成功, task_id={t3['id']}, status={t3['status']}")

    print("\n1.7 查询当前价格 (应为V3)")
    prices = get("open/price/query?brand_code=BRAND_A&site_code=SITE_001")["data"]
    assert len(prices) == 1, f"应有1条生效价格, 实际{len(prices)}"
    p = prices[0]
    elec = [f["price_per_unit"] for f in p["fee_items"] if f["fee_type"] == "electricity"][0]
    svc = [f["price_per_unit"] for f in p["fee_items"] if f["fee_type"] == "service"][0]
    assert elec == 1.5 and svc == 1.0, f"V3价格应为1.5/1.0, 实际{elec}/{svc}"
    print(f"  OK 当前生效: template_id={p['template_id']}, 电费={elec}, 服务费={svc}")

    print("\n1.8 查询价格历史 (V1/V2/V3都可见)")
    history = get("open/price/history?brand_code=BRAND_A&site_code=SITE_001&limit=10")["data"]
    assert len(history) >= 3, f"历史应>=3条, 实际{len(history)}"
    for h in history:
        print(f"    template_id={h['template_id']}, name={h['template_name']}, version={h['template_version']}, status={h['status']}")
    print("  OK 价格历史可查到所有版本")

    print("\n1.9 回滚V3 (应回到V2，不是回到同版本号的别的模板)")
    rb, ok = post(f"publish/tasks/{t3['id']}/rollback", {
        "operator": "admin",
        "remark": "回滚V3",
    })
    assert ok, f"回滚失败: {rb}"
    print(f"  OK 回滚成功, status={rb['status']}")

    print("\n1.10 查询当前价格 (应回到V2)")
    prices = get("open/price/query?brand_code=BRAND_A&site_code=SITE_001")["data"]
    p = prices[0]
    elec = [f["price_per_unit"] for f in p["fee_items"] if f["fee_type"] == "electricity"][0]
    svc = [f["price_per_unit"] for f in p["fee_items"] if f["fee_type"] == "service"][0]
    assert elec == 1.2 and svc == 0.8, f"回滚后应为V2价格1.2/0.8, 实际{elec}/{svc}"
    assert p["template_id"] == v2_id, f"回滚后应回到V2模板(id={v2_id}), 实际id={p['template_id']}"
    print(f"  OK 回滚后生效V2: template_id={p['template_id']}, 电费={elec}, 服务费={svc}")

    print("\n1.11 回滚V2 (应回到V1)")
    rb2, ok = post(f"publish/tasks/{t2['id']}/rollback", {
        "operator": "admin",
        "remark": "回滚V2",
    })
    assert ok, f"回滚V2失败: {rb2}"
    prices = get("open/price/query?brand_code=BRAND_A&site_code=SITE_001")["data"]
    p = prices[0]
    elec = [f["price_per_unit"] for f in p["fee_items"] if f["fee_type"] == "electricity"][0]
    assert elec == 1.0, f"回滚V2后应回到V1价格1.0, 实际{elec}"
    assert p["template_id"] == v1_id, f"回滚后应回到V1模板(id={v1_id}), 实际id={p['template_id']}"
    print(f"  OK 回滚V2后生效V1: template_id={p['template_id']}, 电费={elec}")

    print("\nOK 需求1验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  X 需求1失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ======================================================================
#  需求2：同站点级别冲突检测
# ======================================================================
print("\n" + "=" * 80)
print("  需求2：同站点级别冲突检测，不同模板同站点也触发409")
print("=" * 80)

try:
    print("\n2.1 创建模板B (同站点BRAND_A/SITE_001)")
    tpl_b, ok = create_template("模板B", 1.0, 0.6, brand_code="BRAND_A", site_code="SITE_001")
    assert ok
    tpl_b_id = tpl_b["id"]

    print("\n2.2 给模板B创建定时发布任务 (pending)")
    task_b, ok = post("publish/tasks", {
        "template_id": tpl_b_id,
        "publish_type": "scheduled",
        "scheduled_at": "2030-01-01T00:00:00",
        "operator": "admin",
    })
    assert ok
    print(f"  OK 定时任务创建成功, task_id={task_b['id']}, status={task_b['status']}")

    print("\n2.3 创建模板C (同站点BRAND_A/SITE_001)")
    tpl_c, ok = create_template("模板C", 1.1, 0.7, brand_code="BRAND_A", site_code="SITE_001")
    assert ok
    tpl_c_id = tpl_c["id"]

    print("\n2.4 尝试立即发布模板C (应返回409，因为同站点有pending任务)")
    err, ok = post("publish/tasks", {
        "template_id": tpl_c_id,
        "publish_type": "immediate",
        "operator": "admin",
    }, expect_error=True)
    assert ok, "应返回409冲突"
    err_data = err.get("detail", err) if isinstance(err, dict) else err
    print(f"  接口返回冲突: {json.dumps(err_data, ensure_ascii=False, indent=2)[:300]}")

    print("\n2.5 查询冲突列表 (应有site_conflict)")
    conflicts = get("risk/conflicts")["data"] if isinstance(get("risk/conflicts"), dict) else get("risk/conflicts")
    site_conflicts = [c for c in conflicts if c.get("conflict_type") == "site_conflict"]
    assert len(site_conflicts) >= 1, f"应有site_conflict记录, 实际{len(site_conflicts)}"
    sc = site_conflicts[-1]
    detail = json.loads(sc["conflict_detail"]) if isinstance(sc["conflict_detail"], str) else sc["conflict_detail"]
    print(f"  OK 找到site_conflict, conflict_id={sc['id']}, 挡住的任务: {detail}")

    print("\n2.6 取消模板B的定时任务")
    cancel, ok = post(f"publish/tasks/{task_b['id']}/cancel?operator=admin", {})
    assert ok
    print(f"  OK 任务已取消, status={cancel['status']}")

    print("\n2.7 解决冲突后重新发布模板C")
    resolve, ok = post(f"risk/conflicts/{sc['id']}/resolve", {"resolved_by": "admin"})
    assert ok
    task_c, ok = post("publish/tasks", {
        "template_id": tpl_c_id,
        "publish_type": "immediate",
        "operator": "admin",
    })
    assert ok, f"解决冲突后应能发布: {task_c}"
    print(f"  OK 模板C发布成功, task_id={task_c['id']}, status={task_c['status']}")

    print("\nOK 需求2验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  X 需求2失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ======================================================================
#  需求3：批量重试入口 + final_failed状态
# ======================================================================
print("\n" + "=" * 80)
print("  需求3：批量重试入口 + final_failed状态")
print("=" * 80)

try:
    print("\n3.1 创建新站点模板并发布，获取task_id")
    tpl_d, ok = create_template("模板D-重试测试", 1.0, 0.6, brand_code="BRAND_B", site_code="SITE_002")
    assert ok
    task_d, ok = post("publish/tasks", {
        "template_id": tpl_d["id"],
        "publish_type": "immediate",
        "operator": "admin",
    })
    assert ok

    print("\n3.2 批量创建回执记录 (max_retry=3)")
    receipts, ok = post(f"receipt/batch?task_id={task_d['id']}", ["CH_X", "CH_Y", "CH_Z"])
    assert ok
    receipt_ids = [r["id"] for r in receipts]
    print(f"  OK 创建了 {len(receipt_ids)} 条回执记录: {receipt_ids}")

    print("\n3.3 模拟所有回执失败")
    for rid in receipt_ids:
        receipt = get(f"receipt/records/{rid}")
        post("receipt/callback", {
            "channel_code": receipt["channel_code"],
            "task_id": receipt["task_id"],
            "status": "failed",
            "error_message": "连接超时",
        })
    print("  OK 全部标记为失败")

    print("\n3.4 调用批量重试接口 (第一次)")
    batch1, ok = post("receipt/batch-retry", {})
    assert ok
    print(f"  OK 批量重试: retried_count={batch1['retried_count']}, exhausted_count={batch1['exhausted_count']}")
    assert batch1["retried_count"] == 3, f"应重试3条, 实际{batch1['retried_count']}"

    print("\n3.5 再次标记失败，第二次批量重试")
    for rid in receipt_ids:
        receipt = get(f"receipt/records/{rid}")
        post("receipt/callback", {
            "channel_code": receipt["channel_code"],
            "task_id": receipt["task_id"],
            "status": "failed",
            "error_message": "第二次超时",
        })
    batch2, ok = post("receipt/batch-retry", {})
    assert ok
    print(f"  OK 第二次批量重试: retried_count={batch2['retried_count']}")

    print("\n3.6 再次标记失败，第三次批量重试")
    for rid in receipt_ids:
        receipt = get(f"receipt/records/{rid}")
        post("receipt/callback", {
            "channel_code": receipt["channel_code"],
            "task_id": receipt["task_id"],
            "status": "failed",
            "error_message": "第三次超时",
        })
    batch3, ok = post("receipt/batch-retry", {})
    assert ok
    print(f"  OK 第三次批量重试: retried_count={batch3['retried_count']}")

    print("\n3.7 最后一次标记失败 + 批量重试 (达到max_retry)")
    for rid in receipt_ids:
        receipt = get(f"receipt/records/{rid}")
        if receipt["status"] != "failed":
            post("receipt/callback", {
                "channel_code": receipt["channel_code"],
                "task_id": receipt["task_id"],
                "status": "failed",
                "error_message": "第四次超时-终败",
            })
    batch4, ok = post("receipt/batch-retry", {})
    assert ok
    print(f"  OK 第四次批量重试: retried_count={batch4['retried_count']}, exhausted_count={batch4['exhausted_count']}")
    assert batch4["exhausted_count"] >= 1, f"应有耗尽的记录, 实际{batch4['exhausted_count']}"

    print("\n3.8 检查回执列表中是否有final_failed状态")
    failed_list = get("receipt/records?status=final_failed")
    if isinstance(failed_list, dict):
        failed_list = failed_list.get("data", failed_list)
    assert len(failed_list) >= 1, "应有final_failed记录"
    for r in failed_list:
        print(f"    回执{id}: status={r['status']}, retry_count={r['retry_count']}, max_retry={r['max_retry']}")
        assert r["status"] == "final_failed", f"状态应为final_failed, 实际{r['status']}"

    print("\n3.9 检查每条记录的重试日志")
    for rid in receipt_ids:
        r = get(f"receipt/records/{rid}")
        print(f"    回执{rid}: status={r['status']}, retry_count={r['retry_count']}, max_retry={r['max_retry']}")
        retries = r.get("retries", [])
        print(f"      重试日志共 {len(retries)} 条:")
        for log in retries:
            print(f"        - {log['retry_at'][:19]} status={log['status']} err={log.get('error_message', '')}")
        assert r["retry_count"] == r["max_retry"], f"重试次数应达最大{r['max_retry']}, 实际{r['retry_count']}"

    print("\n  OK 达到最大次数后停止重试，状态标记为final_failed，每轮重试都有日志")
    print("\nOK 需求3验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  X 需求3失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ======================================================================
#  需求4：开放接口串联验证
# ======================================================================
print("\n" + "=" * 80)
print("  需求4：开放接口串联验证，发布/回滚后合作方可查当前生效版本")
print("=" * 80)

try:
    print("\n4.1 创建模板E (BRAND_C/SITE_003)")
    tpl_e, ok = create_template("模板E-V1", 0.8, 0.5, brand_code="BRAND_C", site_code="SITE_003")
    assert ok
    tpl_e_id = tpl_e["id"]

    print("\n4.2 发布模板E")
    task_e, ok = post("publish/tasks", {
        "template_id": tpl_e_id,
        "publish_type": "immediate",
        "operator": "op01",
    })
    assert ok
    task_e_id = task_e["id"]
    print(f"  OK 发布成功, task_id={task_e_id}, status={task_e['status']}")

    print("\n4.3 查询开放接口 - 当前价格")
    price_data = get("open/price/query?brand_code=BRAND_C&site_code=SITE_003")["data"]
    assert len(price_data) == 1
    p = price_data[0]
    elec = [f["price_per_unit"] for f in p["fee_items"] if f["fee_type"] == "electricity"][0]
    print(f"  OK 价格查询: template_id={p['template_id']}, name={p['template_name']}, version={p['template_version']}, 电费={elec}")

    print("\n4.4 检查开放接口返回的publish_status字段")
    pub_status = p.get("publish_status")
    assert pub_status is not None, "应有publish_status字段"
    assert pub_status["status"] == "published", f"publish_status应为published, 实际{pub_status['status']}"
    assert pub_status["task_id"] == task_e_id, f"task_id应对应, 期望{task_e_id}, 实际{pub_status['task_id']}"
    print(f"  OK publish_status: task_id={pub_status['task_id']}, status={pub_status['status']}, operator={pub_status['operator']}")

    print("\n4.5 发布接口结果也包含模板版本信息")
    print(f"    发布接口返回: template_name={task_e.get('template_name')}, template_version={task_e.get('template_version')}, brand_code={task_e.get('brand_code')}, site_code={task_e.get('site_code')}")
    assert task_e.get("brand_code") == "BRAND_C", "发布接口应返回brand_code"
    assert task_e.get("site_code") == "SITE_003", "发布接口应返回site_code"

    print("\n4.6 创建模板E-V2并发布")
    tpl_e2, ok = create_template("模板E-V2", 1.0, 0.7, brand_code="BRAND_C", site_code="SITE_003")
    assert ok
    task_e2, ok = post("publish/tasks", {
        "template_id": tpl_e2["id"],
        "publish_type": "immediate",
        "operator": "op02",
    })
    assert ok
    task_e2_id = task_e2["id"]

    print("\n4.7 查询开放接口 (发布后)")
    price_data = get("open/price/query?brand_code=BRAND_C&site_code=SITE_003")["data"]
    p = price_data[0]
    elec = [f["price_per_unit"] for f in p["fee_items"] if f["fee_type"] == "electricity"][0]
    pub_status = p.get("publish_status")
    assert elec == 1.0, f"V2电费应为1.0, 实际{elec}"
    assert pub_status["status"] == "published", f"应为published, 实际{pub_status['status']}"
    print(f"  OK V2生效: template_id={p['template_id']}, 电费={elec}, publish_status.task_id={pub_status['task_id']}")

    print("\n4.8 回滚V2")
    rb_e2, ok = post(f"publish/tasks/{task_e2_id}/rollback", {
        "operator": "op03",
        "remark": "回滚V2",
    })
    assert ok
    print(f"  OK 回滚成功, status={rb_e2['status']}")
    print(f"    回滚接口返回: brand_code={rb_e2.get('brand_code')}, site_code={rb_e2.get('site_code')}")

    print("\n4.9 查询开放接口 (回滚后)")
    price_data = get("open/price/query?brand_code=BRAND_C&site_code=SITE_003")["data"]
    p = price_data[0]
    elec = [f["price_per_unit"] for f in p["fee_items"] if f["fee_type"] == "electricity"][0]
    pub_status = p.get("publish_status")
    assert elec == 0.8, f"回滚后电费应为0.8, 实际{elec}"
    assert p["template_id"] == tpl_e_id, f"应回到V1模板, 实际id={p['template_id']}"
    print(f"  OK 回滚后: template_id={p['template_id']}, 电费={elec}")

    print("\n4.10 价格历史查询也能串联验证")
    history = get("open/price/history?brand_code=BRAND_C&site_code=SITE_003&limit=10")["data"]
    published_records = [h for h in history if h.get("publish_records")]
    assert len(published_records) >= 2, "历史应有至少2个已发布记录"
    for h in published_records:
        print(f"    template_id={h['template_id']}, name={h['template_name']}, version={h['template_version']}, status={h['status']}")
        for pr in h.get("publish_records", []):
            print(f"      publish_task: id={pr['id']}, type={pr['publish_type']}, status={pr['status']}")
    print("  OK 价格历史与发布记录串联可验证")

    print("\nOK 需求4验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  X 需求4失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ======================================================================
print("\n" + "=" * 80)
print(f"   测试汇总：{pass_count} 通过，{fail_count} 失败")
print("=" * 80)

if fail_count == 0:
    print("\n  所有4大新需求全部验证通过！")
else:
    print(f"\n  有 {fail_count} 个需求未通过，请检查！")
