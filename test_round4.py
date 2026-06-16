import urllib.request
import json
import traceback

BASE = "http://localhost:8000/api/v1"


def post(path, data, expect_error=False, expect_status=None):
    try:
        req = urllib.request.Request(
            f"{BASE}/{path}",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read().decode())
        if expect_error and not expect_status:
            return result, False
        return result, True
    except urllib.error.HTTPError as e:
        err_detail = e.read().decode()
        try:
            err_detail = json.loads(err_detail)
        except Exception:
            pass
        if expect_status and e.code == expect_status:
            return err_detail, True
        if expect_error:
            return err_detail, True
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
print("  全链路测试：4大新需求验证")
print("=" * 80)

# ======================================================================
#  需求1：调价审批策略
# ======================================================================
print("\n" + "=" * 80)
print("  需求1：调价审批策略 - 超涨幅进审批，审批后才能发布")
print("=" * 80)

try:
    print("\n1.1 创建价格上下限规则")
    post("risk/limit-rules", {"brand_code": "BRAND_AP", "fee_type": "electricity", "upper_limit": 5.0, "lower_limit": 0.5, "enabled": True})
    post("risk/limit-rules", {"brand_code": "BRAND_AP", "fee_type": "service", "upper_limit": 3.0, "lower_limit": 0.1, "enabled": True})
    print("  OK 上下限规则创建成功")

    print("\n1.2 创建V1模板并发布 (电费1.0, 服务费0.6)")
    v1, ok = create_template("审批测试-V1", 1.0, 0.6, brand_code="BRAND_AP", site_code="SITE_AP1")
    assert ok, f"V1创建失败: {v1}"
    task1, ok = post("publish/tasks", {"template_id": v1["id"], "publish_type": "immediate", "operator": "admin"})
    assert ok, f"V1发布失败: {task1}"
    print(f"  OK V1发布成功, task_id={task1['id']}")

    print("\n1.3 创建审批策略: 涨幅超过20%需审批")
    strategy, ok = post("risk/approval-strategies", {
        "brand_code": "BRAND_AP",
        "max_increase_pct": 20.0,
    })
    assert ok, f"审批策略创建失败: {strategy}"
    print(f"  OK 审批策略创建成功, id={strategy['id']}, max_increase_pct={strategy['max_increase_pct']}")

    print("\n1.4 创建V2模板 (电费1.5, 涨幅50%) 并尝试发布")
    v2, ok = create_template("审批测试-V2", 1.5, 0.8, brand_code="BRAND_AP", site_code="SITE_AP1")
    assert ok
    err, ok = post("publish/tasks", {"template_id": v2["id"], "publish_type": "immediate", "operator": "admin"}, expect_status=202)
    assert ok, "应返回审批待定状态(202)"
    err_data = err.get("detail", err) if isinstance(err, dict) else err
    print(f"  接口返回: {json.dumps(err_data, ensure_ascii=False)[:300]}")
    assert err_data.get("approval_status") == "pending" or "审批" in json.dumps(err_data, ensure_ascii=False), "应提示需要审批"
    task_id = err_data.get("task_id")
    print(f"  OK 发布被拦截，任务已进入待审批, task_id={task_id}")

    print("\n1.5 查看审批记录")
    approvals = get("risk/approvals?task_id={}".format(task_id))
    assert len(approvals) >= 1, f"应有审批记录, 实际{len(approvals)}"
    approval_id = approvals[0]["id"]
    print(f"  OK 找到审批记录, id={approval_id}, status={approvals[0]['status']}")
    trigger = json.loads(approvals[0]["trigger_detail"]) if isinstance(approvals[0]["trigger_detail"], str) else approvals[0]["trigger_detail"]
    print(f"    触发详情: fee_type={trigger['fee_type']}, 旧价={trigger['old_price']}, 新价={trigger['new_price']}, 涨幅={trigger['increase_pct']}%")

    print("\n1.6 尝试在审批未通过时发布 (应被拦截)")
    err2, ok = post(f"publish/tasks/{task_id}/publish", {}, expect_error=True)
    assert ok, "应被拦截"
    print(f"  OK 审批未通过时发布被拦截")

    print("\n1.7 审批通过")
    for ap in approvals:
        if ap["status"] == "pending":
            approved, ok = post(f"risk/approvals/{ap['id']}/approve", {"operator": "reviewer_zhang"})
            assert ok, f"审批通过失败: {approved}"
            print(f"  OK 审批记录{ap['id']}通过, status={approved['status']}")

    print("\n1.8 审批通过后再发布")
    task2, ok = post(f"publish/tasks/{task_id}/publish", {})
    assert ok, f"审批通过后应能发布: {task2}"
    print(f"  OK 审批通过后发布成功, status={task2['status']}")

    print("\n1.9 查询开放接口 - 验证审批状态")
    prices = get("open/price/query?brand_code=BRAND_AP&site_code=SITE_AP1")["data"]
    p = prices[0]
    ps = p.get("publish_status", {})
    print(f"  当前价格: template_id={p['template_id']}, approval_status={ps.get('approval_status')}")
    assert ps.get("approval_status") == "approved", f"审批状态应为approved, 实际{ps.get('approval_status')}"
    print("  OK 开放接口显示 approval_status=approved")

    print("\nOK 需求1验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  X 需求1失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ======================================================================
#  需求2：按渠道分批灰度发布
# ======================================================================
print("\n" + "=" * 80)
print("  需求2：按渠道分批灰度发布 + 灰度状态查看 + 单渠道回退")
print("=" * 80)

try:
    print("\n2.1 创建灰度测试模板")
    tpl_gs, ok = create_template("灰度测试", 1.2, 0.8, brand_code="BRAND_GS", site_code="SITE_GS1")
    assert ok

    print("\n2.2 创建灰度发布任务 (灰度比例0.3, 渠道CH_A,CH_B,CH_C)")
    task_gs, ok = post("publish/tasks", {
        "template_id": tpl_gs["id"],
        "publish_type": "grayscale",
        "grayscale_ratio": 0.3,
        "grayscale_channel_codes": "CH_A,CH_B,CH_C",
        "operator": "admin",
    })
    assert ok, f"灰度任务创建失败: {task_gs}"
    task_gs_id = task_gs["id"]
    print(f"  OK 灰度任务创建成功, task_id={task_gs_id}, status={task_gs['status']}")

    print("\n2.3 执行灰度发布")
    published, ok = post(f"publish/tasks/{task_gs_id}/publish", {})
    assert ok, f"灰度发布失败: {published}"
    print(f"  OK 灰度发布成功, status={published['status']}")

    print("\n2.4 查看灰度渠道状态")
    gs_status = get(f"publish/tasks/{task_gs_id}/grayscale")
    print(f"  灰度渠道共 {len(gs_status)} 个:")
    for ch in gs_status:
        print(f"    {ch['channel_code']}: ratio={ch['ratio']}, receipt_status={ch['receipt_status']}, is_full={ch['is_full']}")
    assert len(gs_status) == 3, f"应有3个灰度渠道, 实际{len(gs_status)}"
    assert all(ch["ratio"] == 0.3 for ch in gs_status), "所有渠道初始灰度比例应为0.3"
    assert all(not ch["is_full"] for ch in gs_status), "初始均未切全量"
    print("  OK 每个渠道都有灰度比例和回执状态")

    print("\n2.5 为灰度渠道创建回执")
    receipts, ok = post(f"receipt/batch?task_id={task_gs_id}", ["CH_A", "CH_B", "CH_C"])
    assert ok

    print("\n2.6 CH_A回执成功, CH_B回执失败, CH_C回执成功")
    post("receipt/callback", {"channel_code": "CH_A", "task_id": task_gs_id, "status": "success", "response_data": '{"ok":1}'})
    post("receipt/callback", {"channel_code": "CH_B", "task_id": task_gs_id, "status": "failed", "error_message": "CH_B连接超时"})
    post("receipt/callback", {"channel_code": "CH_C", "task_id": task_gs_id, "status": "success", "response_data": '{"ok":1}'})

    print("\n2.7 查看灰度状态 (回执状态应已更新)")
    gs_status2 = get(f"publish/tasks/{task_gs_id}/grayscale")
    for ch in gs_status2:
        print(f"    {ch['channel_code']}: receipt_status={ch['receipt_status']}")
    ch_a = [c for c in gs_status2 if c["channel_code"] == "CH_A"][0]
    ch_b = [c for c in gs_status2 if c["channel_code"] == "CH_B"][0]
    assert ch_a["receipt_status"] == "success", "CH_A应成功"
    assert ch_b["receipt_status"] == "failed", "CH_B应失败"
    print("  OK 回执状态已更新")

    print("\n2.8 只回退失败渠道CH_B (不影响CH_A和CH_C)")
    rb_ch_b, ok = post(f"publish/tasks/{task_gs_id}/grayscale/CH_B/rollback?operator=admin", {})
    assert ok, f"灰度渠道回退失败: {rb_ch_b}"
    print(f"  OK CH_B已回退, receipt_status={rb_ch_b['receipt_status']}, ratio={rb_ch_b['ratio']}")

    print("\n2.9 将CH_A推进到全量")
    promote_ch_a, ok = post(f"publish/tasks/{task_gs_id}/grayscale/CH_A/promote?ratio=1.0", {})
    assert ok
    print(f"  OK CH_A已推进全量, ratio={promote_ch_a['ratio']}, is_full={promote_ch_a['is_full']}")

    print("\n2.10 最终灰度状态")
    gs_final = get(f"publish/tasks/{task_gs_id}/grayscale")
    for ch in gs_final:
        print(f"    {ch['channel_code']}: ratio={ch['ratio']}, receipt_status={ch['receipt_status']}, is_full={ch['is_full']}")
    ch_a_final = [c for c in gs_final if c["channel_code"] == "CH_A"][0]
    ch_b_final = [c for c in gs_final if c["channel_code"] == "CH_B"][0]
    ch_c_final = [c for c in gs_final if c["channel_code"] == "CH_C"][0]
    assert ch_a_final["is_full"], "CH_A应已全量"
    assert ch_b_final["receipt_status"] == "rolled_back", "CH_B应已回退"
    assert ch_c_final["receipt_status"] == "success", "CH_C应保持成功"
    print("  OK 灰度状态正确: CH_A全量, CH_B已回退, CH_C成功")

    print("\nOK 需求2验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  X 需求2失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ======================================================================
#  需求3：按任务维度的重试概览
# ======================================================================
print("\n" + "=" * 80)
print("  需求3：按任务维度的重试概览 + 单渠道重试轨迹")
print("=" * 80)

try:
    print("\n3.1 创建模板并发布")
    tpl_rs, ok = create_template("重试概览测试", 1.0, 0.5, brand_code="BRAND_RS", site_code="SITE_RS1")
    assert ok
    task_rs, ok = post("publish/tasks", {"template_id": tpl_rs["id"], "publish_type": "immediate", "operator": "admin"})
    assert ok
    task_rs_id = task_rs["id"]

    print("\n3.2 批量创建回执")
    receipts, ok = post(f"receipt/batch?task_id={task_rs_id}", ["CH_X", "CH_Y", "CH_Z"])
    assert ok

    print("\n3.3 模拟不同回执结果: CH_X成功, CH_Y失败, CH_Z失败")
    post("receipt/callback", {"channel_code": "CH_X", "task_id": task_rs_id, "status": "success", "response_data": '{"ok":1}'})
    post("receipt/callback", {"channel_code": "CH_Y", "task_id": task_rs_id, "status": "failed", "error_message": "连接超时"})
    post("receipt/callback", {"channel_code": "CH_Z", "task_id": task_rs_id, "status": "failed", "error_message": "服务不可用"})

    print("\n3.4 重试CH_Y (成功)")
    r_y = get("receipt/records?task_id={}".format(task_rs_id))
    y_id = [r for r in r_y if r["channel_code"] == "CH_Y"][0]["id"]
    post(f"receipt/records/{y_id}/retry", {})
    post("receipt/callback", {"channel_code": "CH_Y", "task_id": task_rs_id, "status": "success", "response_data": '{"ok":1}'})

    print("\n3.5 重试CH_Z到max_retry后最终失败")
    z_id = [r for r in r_y if r["channel_code"] == "CH_Z"][0]["id"]
    for i in range(3):
        post(f"receipt/records/{z_id}/retry", {})
        post("receipt/callback", {"channel_code": "CH_Z", "task_id": task_rs_id, "status": "failed", "error_message": f"第{i+2}次超时"})
    post("receipt/batch-retry", {})

    print("\n3.6 查看任务维度的重试概览")
    summary = get(f"receipt/task-summary/{task_rs_id}")
    print(f"  任务 {task_rs_id} 重试概览:")
    print(f"    总数={summary['total']}, 成功={summary['success']}, 失败={summary['failed']}, 最终失败={summary['final_failed']}, 待处理={summary['pending']}")
    assert summary["total"] == 3, f"总数应为3, 实际{summary['total']}"
    assert summary["success"] == 2, f"成功应为2, 实际{summary['success']}"
    assert summary["final_failed"] == 1, f"最终失败应为1, 实际{summary['final_failed']}"

    print("\n  各渠道详情:")
    for ch in summary["channels"]:
        print(f"    {ch['channel_code']}: status={ch['status']}, retry_count={ch['retry_count']}, max_retry={ch['max_retry']}")
        if ch["retries"]:
            for log in ch["retries"]:
                completed = log["completed_at"][:19] if log["completed_at"] else "N/A"
                print(f"      第{log['retry_no']}轮: {log['retry_at'][:19]} -> {completed}, status={log['status']}")

    print("\n3.7 点进CH_Z查看完整重试轨迹")
    ch_z = [c for c in summary["channels"] if c["channel_code"] == "CH_Z"][0]
    assert ch_z["status"] == "final_failed", f"CH_Z应为final_failed, 实际{ch_z['status']}"
    assert len(ch_z["retries"]) >= 3, f"CH_Z应有>=3轮重试, 实际{len(ch_z['retries'])}"
    print(f"  OK CH_Z: status={ch_z['status']}, {len(ch_z['retries'])}轮重试记录, 每轮都有发起→完成时间")
    print("\nOK 需求3验证通过！")
    pass_count += 1
except Exception as e:
    print(f"  X 需求3失败: {e}")
    traceback.print_exc()
    fail_count += 1

# ======================================================================
#  需求4：冻结站点创建模板时也拦截
# ======================================================================
print("\n" + "=" * 80)
print("  需求4：冻结站点创建模板时也拦截，解冻后恢复")
print("=" * 80)

try:
    print("\n4.1 先创建模板 (冻结前)")
    tpl_fr, ok = create_template("冻结测试模板", 1.0, 0.5, brand_code="BRAND_FR", site_code="SITE_FR", version=1)
    assert ok, f"冻结前应能创建模板: {tpl_fr}"
    print(f"  OK 模板创建成功, id={tpl_fr['id']}")

    print("\n4.2 冻结SITE_FR站点")
    freeze, ok = post("risk/freeze", {
        "region_code": "SITE_FR",
        "region_name": "冻结测试区域",
        "reason": "系统维护",
        "operator": "admin",
    })
    assert ok
    freeze_id = freeze["id"]
    print(f"  OK 站点冻结成功, freeze_id={freeze_id}")

    print("\n4.3 冻结后创建模板 (应被拦截)")
    err, ok = create_template("冻结测试模板2", 1.0, 0.5, brand_code="BRAND_FR", site_code="SITE_FR", version=2)
    assert ok == False or (isinstance(err, dict) and "冻结" in json.dumps(err, ensure_ascii=False)), "应被冻结拦截"
    print(f"  OK 创建模板被拦截: {json.dumps(err, ensure_ascii=False)[:200]}")

    print("\n4.4 冻结后发布已有模板也应被拦截")
    err2, ok2 = post("publish/tasks", {"template_id": tpl_fr["id"], "publish_type": "immediate", "operator": "admin"}, expect_error=True)
    assert ok2, "发布也应被冻结拦截"
    print(f"  OK 发布也被拦截")

    print("\n4.5 解冻站点")
    lifted, ok = post(f"risk/freeze/{freeze_id}/lift?operator=admin", {})
    assert ok
    print(f"  OK 解冻成功, status={lifted['status']}")

    print("\n4.6 解冻后同样的创建请求能成功")
    tpl_after, ok = create_template("解冻后模板", 1.0, 0.5, brand_code="BRAND_FR", site_code="SITE_FR", version=2)
    assert ok, f"解冻后应能创建模板: {tpl_after}"
    print(f"  OK 解冻后创建成功, template_id={tpl_after['id']}")

    print("\n4.7 解冻后发布也能成功")
    task_fr, ok = post("publish/tasks", {"template_id": tpl_after["id"], "publish_type": "immediate", "operator": "admin"})
    assert ok, f"解冻后应能发布: {task_fr}"
    print(f"  OK 解冻后发布成功, status={task_fr['status']}")

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
    print("\n  所有4个新需求全部验证通过！")
else:
    print(f"\n  有 {fail_count} 个需求未通过，请检查！")
