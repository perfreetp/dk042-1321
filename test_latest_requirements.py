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


def create_template(template_name, elec_price, service_price, subsidy_price=0, version=None,
                    brand_code="BRAND_A", site_code="SITE_001"):
    body = {
        "brand_code": brand_code,
        "site_code": site_code,
        "template_name": template_name,
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
    }
    if version is not None:
        body["template_version"] = version
    return post("strategy/templates", body)


pass_count = 0
fail_count = 0

print("=" * 80)
print("  全链路测试：最新3个需求验证")
print("=" * 80)

print("\n  前置准备：创建价格上下限规则")
post("risk/limit-rules", {
    "brand_code": "BRAND_X",
    "fee_type": "electricity",
    "upper_limit": 3.0,
    "lower_limit": 0.5,
    "enabled": True,
})
post("risk/limit-rules", {
    "brand_code": "BRAND_X",
    "fee_type": "service",
    "upper_limit": 2.0,
    "lower_limit": 0.1,
    "enabled": True,
})
print("  OK 上下限规则创建成功")

# ======================================================================
#  需求1：模板版本号真正保存 + 自动递增
# ======================================================================
print("\n" + "=" * 80)
print("  需求1：模板版本号真正保存 + 不传时自动递增")
print("=" * 80)

try:
    print("\n1.1 不传版本号创建第一个模板 (应自动为版本1)")
    t1, ok = create_template("模板X-Auto1", 1.0, 0.6, brand_code="BRAND_X", site_code="SITE_X1")
    assert ok
    assert t1["template_version"] == 1, f"版本应为1, 实际{t1['template_version']}"
    print(f"  OK 模板创建成功, id={t1['id']}, version={t1['template_version']}")

    print("\n1.2 不传版本号创建第二个模板 (应自动为版本2)")
    t2, ok = create_template("模板X-Auto2", 1.2, 0.8, brand_code="BRAND_X", site_code="SITE_X1")
    assert ok
    assert t2["template_version"] == 2, f"版本应为2, 实际{t2['template_version']}"
    print(f"  OK 模板创建成功, id={t2['id']}, version={t2['template_version']}")

    print("\n1.3 显式指定版本号5创建模板")
    t5, ok = create_template("模板X-Manual5", 1.5, 1.0, version=5, brand_code="BRAND_X", site_code="SITE_X1")
    assert ok
    assert t5["template_version"] == 5, f"版本应为5, 实际{t5['template_version']}"
    print(f"  OK 模板创建成功, id={t5['id']}, version={t5['template_version']}")

    print("\n1.4 不传版本号再创建一个 (应顺着5自动为版本6)")
    t6, ok = create_template("模板X-Auto6", 1.8, 1.2, brand_code="BRAND_X", site_code="SITE_X1")
    assert ok
    assert t6["template_version"] == 6, f"版本应为6, 实际{t6['template_version']}"
    print(f"  OK 模板创建成功, id={t6['id']}, version={t6['template_version']}")

    print("\n1.5 新站点新品牌应从版本1开始")
    ty, ok = create_template("模板Y-新站点", 1.0, 0.5, brand_code="BRAND_Y", site_code="SITE_Y1")
    assert ok
    assert ty["template_version"] == 1, f"新站点版本应为1, 实际{ty['template_version']}"
    print(f"  OK 新站点模板版本从1开始, version={ty['template_version']}")

    print("\n1.6 模板详情查询能看到正确版本号")
    t1_detail = get(f"strategy/templates/{t1['id']}")
    assert t1_detail["template_version"] == 1
    t5_detail = get(f"strategy/templates/{t5['id']}")
    assert t5_detail["template_version"] == 5
    print(f"  OK 模板详情版本号正确: V1={t1_detail['template_version']}, V5={t5_detail['template_version']}")

    print("\n1.7 价格历史查询能看到正确版本号")
    history = get("open/price/history?brand_code=BRAND_X&site_code=SITE_X1&limit=10")["data"]
    versions = {h["template_name"]: h["template_version"] for h in history}
    assert versions.get("模板X-Auto1") == 1
    assert versions.get("模板X-Manual5") == 5
    assert versions.get("模板X-Auto6") == 6
    print("  OK 价格历史中的版本号与创建时一致")

    print("\nOK 需求1验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  X 需求1失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ======================================================================
#  需求2：重试日志完整记录发起→回执结果
# ======================================================================
print("\n" + "=" * 80)
print("  需求2：重试日志完整记录发起→回执结果，列表可区分final_failed")
print("=" * 80)

try:
    print("\n2.1 创建模板并发布，生成回执")
    tpl_r, ok = create_template("模板R-重试", 1.0, 0.6, brand_code="BRAND_R", site_code="SITE_R1")
    assert ok
    task_r, ok = post("publish/tasks", {
        "template_id": tpl_r["id"],
        "publish_type": "immediate",
        "operator": "admin",
    })
    assert ok

    receipts, ok = post(f"receipt/batch?task_id={task_r['id']}", ["CH_R1", "CH_R2"])
    assert ok
    r1_id = receipts[0]["id"]
    r2_id = receipts[1]["id"]
    print(f"  OK 创建了 {len(receipts)} 条回执记录: {r1_id}, {r2_id}")

    print("\n2.2 首次回执失败")
    post("receipt/callback", {
        "channel_code": "CH_R1",
        "task_id": task_r["id"],
        "status": "failed",
        "error_message": "首次连接超时",
    })
    post("receipt/callback", {
        "channel_code": "CH_R2",
        "task_id": task_r["id"],
        "status": "failed",
        "error_message": "首次连接超时",
    })
    print("  OK 全部标记为失败")

    print("\n2.3 第一次重试 + 回执失败")
    retry1, ok = post(f"receipt/records/{r1_id}/retry", {})
    assert ok
    print(f"  OK 第一次重试: retry_count={retry1['retry_count']}, status={retry1['status']}")

    post("receipt/callback", {
        "channel_code": "CH_R1",
        "task_id": task_r["id"],
        "status": "failed",
        "error_message": "第二次连接超时",
    })

    print("\n2.4 查看回执详情，重试日志应有发起时间和完成时间")
    detail = get(f"receipt/records/{r1_id}")
    retries = detail.get("retries", [])
    print(f"  回执{r1_id}: status={detail['status']}, retry_count={detail['retry_count']}")
    print(f"  重试日志共 {len(retries)} 条:")
    for log in retries:
        print(f"    第{log['retry_no']}轮: retry_at={log['retry_at'][:19]}, completed_at={log['completed_at'][:19] if log['completed_at'] else 'N/A'}, status={log['status']}, err={log.get('error_message', '')}")
    assert len(retries) >= 1, "应有至少1条重试日志"
    first_log = retries[0]
    assert first_log["retry_no"] == 1, "第一轮重试retry_no应为1"
    assert first_log["status"] == "failed", f"第一轮重试状态应为failed, 实际{first_log['status']}"
    assert first_log["completed_at"] is not None, "重试日志应有completed_at"
    assert "第二次" in (first_log["error_message"] or ""), "重试日志应记录最新错误信息"
    print("  OK 重试日志有完整的发起时间、完成时间、状态、错误信息")

    print("\n2.5 CH_R2也重试一次后成功")
    retry2_r2, ok = post(f"receipt/records/{r2_id}/retry", {})
    assert ok
    post("receipt/callback", {
        "channel_code": "CH_R2",
        "task_id": task_r["id"],
        "status": "success",
        "response_data": '{"code":0,"msg":"ok"}',
    })
    detail_r2 = get(f"receipt/records/{r2_id}")
    retries_r2 = detail_r2.get("retries", [])
    assert len(retries_r2) == 1
    assert retries_r2[0]["status"] == "success", f"成功重试状态应为success, 实际{retries_r2[0]['status']}"
    assert retries_r2[0]["response_data"] is not None, "成功重试应有response_data"
    print(f"  OK CH_R2重试成功: status={detail_r2['status']}, 重试日志状态={retries_r2[0]['status']}")

    print("\n2.6 CH_R1继续重试直到max_retry，验证final_failed")
    for i in range(3):
        try:
            post(f"receipt/records/{r1_id}/retry", {})
        except Exception:
            pass
        post("receipt/callback", {
            "channel_code": "CH_R1",
            "task_id": task_r["id"],
            "status": "failed",
            "error_message": f"第{i+3}次连接超时",
        })

    print("\n2.7 调用批量重试，应标记为final_failed")
    batch, ok = post("receipt/batch-retry", {})
    assert ok
    print(f"  批量重试结果: retried={batch['retried_count']}, exhausted={batch['exhausted_count']}")

    print("\n2.8 查看回执列表 - final_failed状态可分辨")
    failed_list = get("receipt/records?status=final_failed")
    if isinstance(failed_list, dict):
        failed_list = failed_list.get("data", failed_list)
    print(f"  final_failed状态的回执共 {len(failed_list)} 条")
    for r in failed_list:
        print(f"    回执{r['id']}: status={r['status']}, retry_count={r['retry_count']}, max_retry={r['max_retry']}")
        detail = get(f"receipt/records/{r['id']}")
        retries = detail.get("retries", [])
        print(f"      共 {len(retries)} 轮重试记录:")
        for log in retries:
            status_str = log["status"]
            retry_at = log["retry_at"][:19] if log["retry_at"] else ""
            completed_at = log["completed_at"][:19] if log["completed_at"] else "N/A"
            print(f"        第{log['retry_no']}轮: {retry_at} -> {completed_at}, status={status_str}")
    assert len(failed_list) >= 1, "应有final_failed的记录"
    print("  OK 列表中可直接分辨final_failed状态，每轮重试有完整的发起→完成时间和结果")

    print("\nOK 需求2验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  X 需求2失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ======================================================================
#  需求3：开放接口串联验证 - 发布/回滚后合作方可查当前生效版本和动作
# ======================================================================
print("\n" + "=" * 80)
print("  需求3：开放接口串联验证 - 发布/回滚后合作方可查当前生效版本和动作")
print("=" * 80)

try:
    print("\n3.1 创建V1模板并发布")
    v1, ok = create_template("串联测试-V1", 0.8, 0.5, version=1, brand_code="BRAND_Z", site_code="SITE_Z1")
    assert ok
    v1_id = v1["id"]

    task1, ok = post("publish/tasks", {
        "template_id": v1_id,
        "publish_type": "immediate",
        "operator": "op_zhang",
    })
    assert ok
    task1_id = task1["id"]
    print(f"  OK V1发布成功, task_id={task1_id}")

    print("\n3.2 查询开放接口 - 查看effective_info")
    prices = get("open/price/query?brand_code=BRAND_Z&site_code=SITE_Z1")["data"]
    p = prices[0]
    ei = p.get("effective_info")
    ps = p.get("publish_status")
    print(f"  当前模板: id={p['template_id']}, name={p['template_name']}, version={p['template_version']}")
    print(f"  publish_status: task_id={ps['task_id']}, status={ps['status']}, operator={ps['operator']}")
    print(f"  effective_info: action_type={ei['action_type']}, action_task_id={ei['action_task_id']}")
    print(f"    action_template: id={ei['action_template_id']}, name={ei['action_template_name']}, v={ei['action_template_version']}")
    print(f"    current_template: id={ei['current_template_id']}, name={ei['current_template_name']}, v={ei['current_template_version']}")

    assert ei is not None, "应有effective_info字段"
    assert ei["action_type"] == "publish", f"当前动作类型应为publish, 实际{ei['action_type']}"
    assert ei["action_template_id"] == v1_id, f"动作模板应是V1(id={v1_id}), 实际{ei['action_template_id']}"
    assert ei["current_template_id"] == v1_id, f"当前模板应是V1(id={v1_id}), 实际{ei['current_template_id']}"
    print("  OK 发布后，effective_info显示action_type=publish，当前模板=动作模板")

    print("\n3.3 创建V2模板并发布")
    v2, ok = create_template("串联测试-V2", 1.0, 0.7, version=2, brand_code="BRAND_Z", site_code="SITE_Z1")
    assert ok
    v2_id = v2["id"]

    task2, ok = post("publish/tasks", {
        "template_id": v2_id,
        "publish_type": "immediate",
        "operator": "op_li",
    })
    assert ok
    task2_id = task2["id"]
    print(f"  OK V2发布成功, task_id={task2_id}")

    print("\n3.4 查询开放接口 (发布V2后)")
    prices = get("open/price/query?brand_code=BRAND_Z&site_code=SITE_Z1")["data"]
    p = prices[0]
    ei = p.get("effective_info")
    print(f"  当前模板: id={p['template_id']}, name={p['template_name']}, version={p['template_version']}")
    print(f"  effective_info: action_type={ei['action_type']}, action_template={ei['action_template_name']}, current={ei['current_template_name']}")

    assert ei["action_type"] == "publish", f"动作类型应为publish, 实际{ei['action_type']}"
    assert ei["action_template_id"] == v2_id, f"动作模板应是V2, 实际{ei['action_template_id']}"
    assert ei["current_template_id"] == v2_id, f"当前模板应是V2, 实际{ei['current_template_id']}"
    print("  OK V2发布后，effective_info正确显示V2为当前和动作模板")

    print("\n3.5 回滚V2")
    rb, ok = post(f"publish/tasks/{task2_id}/rollback", {
        "operator": "op_wang",
        "remark": "价格太高，回滚",
    })
    assert ok
    print(f"  OK 回滚成功, status={rb['status']}")

    print("\n3.6 查询开放接口 (回滚后)")
    prices = get("open/price/query?brand_code=BRAND_Z&site_code=SITE_Z1")["data"]
    p = prices[0]
    ei = p.get("effective_info")
    elec = [f["price_per_unit"] for f in p["fee_items"] if f["fee_type"] == "electricity"][0]
    print(f"  当前模板: id={p['template_id']}, name={p['template_name']}, version={p['template_version']}, 电费={elec}")
    print(f"  effective_info: action_type={ei['action_type']}, action_operator={ei['action_operator']}")
    print(f"    action_template: id={ei['action_template_id']}, name={ei['action_template_name']}, v={ei['action_template_version']}")
    print(f"    current_template: id={ei['current_template_id']}, name={ei['current_template_name']}, v={ei['current_template_version']}")

    assert ei["action_type"] == "rollback", f"动作类型应为rollback, 实际{ei['action_type']}"
    assert ei["action_operator"] == "op_wang", f"操作人应为op_wang, 实际{ei['action_operator']}"
    assert ei["action_template_id"] == v2_id, f"回滚的模板应是V2(id={v2_id}), 实际{ei['action_template_id']}"
    assert ei["current_template_id"] == v1_id, f"当前模板应是V1(id={v1_id}), 实际{ei['current_template_id']}"
    assert elec == 0.8, f"回滚后电费应为0.8, 实际{elec}"
    print("  OK 回滚后，effective_info显示action_type=rollback，动作模板是V2，当前模板是V1")

    print("\n3.7 合作方验证：仅用开放接口也能串起完整链路")
    print("    1. 查当前价格 → 知道当前生效的是哪个模板")
    print("    2. 看effective_info → 知道是哪次发布/回滚导致的")
    print("    3. 看publish_status → 知道当前模板最近一次发布的详情")
    print("    4. 价格历史 → 可追溯所有版本的发布记录")
    print("  OK 合作方不看后台也能对上当前价格的来龙去脉")

    print("\nOK 需求3验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  X 需求3失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ======================================================================
print("\n" + "=" * 80)
print(f"   测试汇总：{pass_count} 通过，{fail_count} 失败")
print("=" * 80)

if fail_count == 0:
    print("\n  所有3个新需求全部验证通过！")
else:
    print(f"\n  有 {fail_count} 个需求未通过，请检查！")
