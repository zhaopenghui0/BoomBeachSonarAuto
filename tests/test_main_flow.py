import importlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np


class FakeAdb:
    instances = []

    def __init__(self, *args, **kwargs):
        self.calls = []
        self.weak_network_enabled = False
        self.reject_network_enabled = False
        FakeAdb.instances.append(self)

    def delay(self, seconds):
        self.calls.append(("delay", seconds))
        return self

    def close_app(self, package_name):
        self.calls.append(("close_app", package_name))

    def open_app(self, package_name):
        self.calls.append(("open_app", package_name))
        return self

    def click(self, x, y):
        self.calls.append(("click", x, y))

    def read_screenshot(self, output_path=None):
        self.calls.append(("read_screenshot", output_path))
        return object()

    def swipe(self, start_x, start_y, end_x, end_y):
        self.calls.append(("swipe", start_x, start_y, end_x, end_y))
        return self

    def enable_weak_network(self, package_name):
        self.calls.append(("enable_weak_network", package_name))
        self.weak_network_enabled = True

    def disable_weak_network(self, package_name):
        self.calls.append(("disable_weak_network", package_name))
        self.weak_network_enabled = False

    def enable_reject_network(self, package_name):
        self.calls.append(("enable_reject_network", package_name))
        self.reject_network_enabled = True

    def disable_reject_network(self, package_name):
        self.calls.append(("disable_reject_network", package_name))
        self.reject_network_enabled = False

    def is_weak_network_enabled(self, package_name):
        self.calls.append(("is_weak_network_enabled", package_name))
        return self.weak_network_enabled

    def is_reject_network_enabled(self, package_name):
        self.calls.append(("is_reject_network_enabled", package_name))
        return self.reject_network_enabled

    def ensure_root_shell(self):
        self.calls.append(("ensure_root_shell",))


class DummyMatch:
    def __init__(self, center):
        self.center = center


class MainFlowTest(unittest.TestCase):
    def setUp(self):
        FakeAdb.instances.clear()
        self.utils = importlib.import_module("utils")
        self.original_adb_controller = self.utils.AdbController
        self.utils.AdbController = FakeAdb
        sys.modules.pop("main", None)
        self.main = importlib.import_module("main")
        self.adb = self.main.adb

    def tearDown(self):
        sys.modules.pop("main", None)
        self.utils.AdbController = self.original_adb_controller
        FakeAdb.instances.clear()

    def test_manual_recovery_offer_cancel_keeps_network_rules_untouched(self):
        self.adb.weak_network_enabled = True
        self.adb.reject_network_enabled = True

        result = self.main.offer_manual_network_recovery(lambda: False)

        self.assertFalse(result)
        self.assertTrue(self.adb.weak_network_enabled)
        self.assertTrue(self.adb.reject_network_enabled)
        self.assertEqual(self.adb.calls, [])

    def test_manual_recovery_offer_clears_rules_without_clicking_game(self):
        package_name = self.main.GAME_PACKAGE_NAME
        self.adb.weak_network_enabled = True
        self.adb.reject_network_enabled = True

        result = self.main.offer_manual_network_recovery(lambda: True)

        self.assertTrue(result)
        self.assertFalse(self.adb.weak_network_enabled)
        self.assertFalse(self.adb.reject_network_enabled)
        self.assertNotIn("click", [call[0] for call in self.adb.calls])
        disable_reject = self.adb.calls.index(("disable_reject_network", package_name))
        disable_drop = self.adb.calls.index(("disable_weak_network", package_name))
        self.assertLess(disable_reject, disable_drop)

    def test_manual_recovery_offer_reports_failure_when_drop_remains(self):
        self.adb.weak_network_enabled = True

        def leave_drop_enabled(package_name):
            self.adb.calls.append(("disable_weak_network", package_name))

        self.adb.disable_weak_network = leave_drop_enabled
        result = self.main.offer_manual_network_recovery(lambda: True)

        self.assertFalse(result)
        self.assertTrue(self.adb.weak_network_enabled)

    def test_enter_activity_recovers_after_activity_button_missing(self):
        waits = iter(
            [
                None,
                DummyMatch((10, 20)),
                DummyMatch((30, 40)),
                DummyMatch((50, 60)),
            ]
        )

        with patch.object(
            self.main,
            "wait_until_occur",
            side_effect=lambda *args, **kwargs: next(waits),
        ):
            self.main.enter_activity(max_retries=2)

        package_name = self.main.GAME_PACKAGE_NAME
        self.assertEqual(self.adb.calls.count(("close_app", package_name)), 1)
        self.assertEqual(self.adb.calls.count(("open_app", package_name)), 1)
        self.assertIn(("click", 10, 20), self.adb.calls)
        self.assertIn(("click", 30, 40), self.adb.calls)
        self.assertIn(("click", 1205, 644), self.adb.calls)
        self.assertEqual(self.adb.calls.count(("enable_weak_network", package_name)), 1)
        self.assertEqual(
            [
                call
                for call in self.adb.calls
                if call == ("swipe", 1000, 660, 1000, 180)
            ],
            [
                ("swipe", 1000, 660, 1000, 180),
                ("swipe", 1000, 660, 1000, 180),
            ],
        )

    def test_enter_activity_stops_after_max_retries(self):
        with patch.object(self.main, "wait_until_occur", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "最大重试次数 2"):
                self.main.enter_activity(max_retries=2)

        package_name = self.main.GAME_PACKAGE_NAME
        self.assertEqual(self.adb.calls.count(("close_app", package_name)), 2)
        self.assertEqual(self.adb.calls.count(("open_app", package_name)), 2)

    def test_re_enter_skips_first_enter_only_actions(self):
        waits = iter(
            [
                DummyMatch((30, 40)),
                DummyMatch((50, 60)),
            ]
        )

        with patch.object(
            self.main,
            "wait_until_occur",
            side_effect=lambda *args, **kwargs: next(waits),
        ):
            self.main.enter_activity(re_enter=True, max_retries=1)

        package_name = self.main.GAME_PACKAGE_NAME
        self.assertNotIn(("enable_weak_network", package_name), self.adb.calls)
        self.assertNotIn(("swipe", 1000, 660, 1000, 180), self.adb.calls)
        self.assertIn(("click", 30, 40), self.adb.calls)
        self.assertIn(("click", 1205, 644), self.adb.calls)

    def test_re_enter_failure_does_not_use_normal_restart_recovery(self):
        with patch.object(self.main, "wait_until_occur", return_value=None):
            with self.assertRaisesRegex(
                self.main.ProbeProtocolError,
                "第二次进入活动",
            ):
                self.main.enter_activity(re_enter=True, max_retries=1)

        package_name = self.main.GAME_PACKAGE_NAME
        self.assertNotIn(("close_app", package_name), self.adb.calls)
        self.assertNotIn(("open_app", package_name), self.adb.calls)
        self.assertNotIn(("disable_weak_network", package_name), self.adb.calls)

    def test_cleanup_keeps_drop_when_probe_request_may_be_pending(self):
        transaction = self.main.ProbeTransaction(level=1, cell=(0, 0), index=0)
        transaction.advance(self.main.ProbePhase.REQUEST_PENDING)
        self.main._active_probe = transaction

        self.main.cleanup_weak_network("测试清理")

        package_name = self.main.GAME_PACKAGE_NAME
        self.assertNotIn(("disable_weak_network", package_name), self.adb.calls)
        self.assertFalse(self.main._weak_network_cleanup_done)

    def test_probe_transaction_preserves_network_order(self):
        waits = iter(
            [
                DummyMatch((1, 1)),  # 点击前已在详情页
                DummyMatch((10, 20)),  # 第二次进入：活动按钮
                DummyMatch((30, 40)),  # 第二次进入：详情页
                DummyMatch((50, 60)),  # REJECT 后的重试按钮
                DummyMatch((70, 80)),  # 登录后下一轮：活动按钮
                DummyMatch((90, 100)),  # 登录后下一轮：详情页
            ]
        )
        hit_map = [[0, 0], [0, 0]]

        with (
            patch.object(
                self.main,
                "wait_until_occur",
                side_effect=lambda *args, **kwargs: next(waits),
            ),
            patch.object(self.main, "click_template", return_value=True),
            patch.object(self.main, "is_diamond_hit", return_value=True),
        ):
            result = self.main._probe_cell(
                level=1,
                hit_map=hit_map,
                cell=(0, 1),
                point=(400, 300),
                index=1,
            )

        package_name = self.main.GAME_PACKAGE_NAME
        network_calls = [
            call
            for call in self.adb.calls
            if call[0]
            in {
                "enable_reject_network",
                "disable_reject_network",
                "disable_weak_network",
                "enable_weak_network",
            }
        ]
        self.assertTrue(result)
        self.assertEqual(hit_map[0][1], 1)
        self.assertIsNone(self.main._active_probe)
        self.assertEqual(
            network_calls,
            [
                ("enable_reject_network", package_name),
                ("disable_reject_network", package_name),
                ("disable_weak_network", package_name),
                ("enable_weak_network", package_name),
            ],
        )

    def test_missing_retry_keeps_probe_pending_and_does_not_restore_drop(self):
        waits = iter(
            [
                DummyMatch((1, 1)),  # 点击前已在详情页
                DummyMatch((10, 20)),  # 第二次进入：活动按钮
                DummyMatch((30, 40)),  # 第二次进入：详情页
                None,  # REJECT 后没有重试按钮
            ]
        )
        hit_map = [[0, 0], [0, 0]]

        with (
            patch.object(
                self.main,
                "wait_until_occur",
                side_effect=lambda *args, **kwargs: next(waits),
            ),
            patch.object(self.main, "click_template", return_value=True),
            patch.object(self.main, "is_diamond_hit", return_value=False),
        ):
            with self.assertRaisesRegex(
                self.main.ProbeProtocolError,
                "未出现重试按钮",
            ):
                self.main._probe_cell(
                    level=1,
                    hit_map=hit_map,
                    cell=(0, 1),
                    point=(400, 300),
                    index=1,
                )

        package_name = self.main.GAME_PACKAGE_NAME
        self.assertIsNotNone(self.main._active_probe)
        self.assertTrue(self.main._active_probe.request_may_be_pending)
        self.assertIn(("enable_reject_network", package_name), self.adb.calls)
        self.assertNotIn(("disable_weak_network", package_name), self.adb.calls)

    def test_preflight_failure_retries_the_same_cell(self):
        hit_map = [[0, 0], [0, 0]]

        with (
            patch.object(
                self.main,
                "_execute_probe_transaction",
                side_effect=[
                    self.main.ProbeNotReadyError("页面未准备好"),
                    False,
                ],
            ) as execute,
            patch.object(self.main, "enter_activity") as recover,
        ):
            result = self.main._probe_cell(
                level=1,
                hit_map=hit_map,
                cell=(0, 1),
                point=(400, 300),
                index=1,
            )

        self.assertFalse(result)
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(execute.call_args_list[0], execute.call_args_list[1])
        recover.assert_called_once_with()

    def test_saved_grid_validation_accepts_small_corner_drift(self):
        saved = np.array([[100, 10], [200, 100], [100, 200], [10, 100]])
        detected = saved + np.array([[2, -1], [1, 2], [-2, 1], [-1, -2]])

        self.assertTrue(
            self.main._saved_grid_matches_current(saved, detected, (720, 1280, 3))
        )

    def test_saved_grid_validation_rejects_stale_points(self):
        saved = np.array([[664, 48], [1069, 288], [671, 625], [259, 290]])
        detected = np.array([[668, 148], [930, 315], [656, 539], [502, 239]])

        self.assertFalse(
            self.main._saved_grid_matches_current(saved, detected, (720, 1280, 3))
        )

    def test_click_point_validation_accepts_points_inside_current_grid(self):
        quad = np.array([[10, 0], [20, 10], [10, 20], [0, 10]])
        points = [(10, 4), (16, 10), (10, 16), (4, 10)]

        self.main._validate_click_points(
            points,
            quad,
            (30, 30, 3),
            expected_count=4,
        )

    def test_click_point_validation_rejects_point_outside_current_grid(self):
        quad = np.array([[10, 0], [20, 10], [10, 20], [0, 10]])
        points = [(10, 4), (16, 10), (10, 16), (29, 29)]

        with self.assertRaisesRegex(RuntimeError, "白色网格外"):
            self.main._validate_click_points(
                points,
                quad,
                (30, 30, 3),
                expected_count=4,
            )

    def test_click_point_validation_rejects_duplicate_coordinates(self):
        quad = np.array([[10, 0], [20, 10], [10, 20], [0, 10]])
        points = [(10, 4), (16, 10), (10, 16), (10, 16)]

        with self.assertRaisesRegex(RuntimeError, "重复坐标"):
            self.main._validate_click_points(
                points,
                quad,
                (30, 30, 3),
                expected_count=4,
            )

    def test_get_click_points_replaces_stale_saved_points(self):
        saved_points = [(0, 0)] * 100
        saved_quad = np.array([[664, 48], [1069, 288], [671, 625], [259, 290]])
        detected_points = [
            (655 + (col - row) * 10, 230 + (row + col) * 10)
            for row in range(10)
            for col in range(10)
        ]
        detected_quad = np.array([[653, 148], [930, 311], [663, 539], [383, 315]])
        detected = SimpleNamespace(points=detected_points, global_quad=detected_quad)
        grid_img = np.zeros((720, 1280, 3), dtype=np.uint8)

        with (
            patch.object(self.main, "read_saved_points", return_value=saved_points),
            patch.object(self.main, "read_saved_quad", return_value=saved_quad),
            patch.object(self.main, "detect_diamond_centers", return_value=detected),
        ):
            points, quad = self.main.get_click_points(9, grid_img)

        self.assertEqual(points, detected_points)
        np.testing.assert_array_equal(quad, detected_quad)

    def test_get_click_points_stops_when_saved_points_cannot_be_verified(self):
        saved_points = [(0, 0)] * 100
        saved_quad = np.array([[664, 48], [1069, 288], [671, 625], [259, 290]])
        grid_img = np.zeros((720, 1280, 3), dtype=np.uint8)

        with (
            patch.object(self.main, "read_saved_points", return_value=saved_points),
            patch.object(self.main, "read_saved_quad", return_value=saved_quad),
            patch.object(
                self.main,
                "detect_diamond_centers",
                side_effect=ValueError("grid not found"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "为避免误点已中止探测"):
                self.main.get_click_points(9, grid_img)

    def test_strategy_fallback_does_not_skip_inferred_safety_area(self):
        strategy = SimpleNamespace(
            done=False,
            shots={(0, 0): False},
            blocked_cells={(0, 1), (1, 0)},
            choose_next_cell=lambda: None,
            get_confirmed_ships=lambda: [],
        )
        progress_bar = MagicMock()
        progress_context = MagicMock()
        progress_context.__enter__.return_value = progress_bar

        with (
            patch.object(self.main, "SubmarineStrategy", return_value=strategy),
            patch.object(self.main, "fixed_progress_bar", return_value=progress_context),
            patch.object(self.main, "update_fixed_progress"),
            patch.object(self.main, "_scan_level_by_grid_order") as fallback,
        ):
            self.main._scan_level_by_strategy(
                level=1,
                hit_map=[[0, 0, 0] for _ in range(3)],
                click_points=[(0, 0)] * 9,
                submarines=[3],
            )

        fallback.assert_called_once()
        self.assertEqual(fallback.call_args.kwargs["skip_cells"], {(0, 0)})


if __name__ == "__main__":
    unittest.main()
