"""
ADVERSARIAL TESTS FOR STRICT CAPABILITIES

Proving IMPOSSIBILITY of escalation.
Tests demonstrate non-escalation by showing failures.

Build Prompt: CAPABILITY EXPANSION UNDER MEK
"""

from __future__ import annotations

import pytest
import tempfile
import os
from pathlib import Path
from typing import Dict, Any

from backend.core.capabilities.filesystem_strict import (
    FilesystemRead,
    FilesystemWrite,
    FilesystemDelete,
    FilesystemRefusal,
    FilesystemError,
    FilesystemConfig,
)

from backend.core.capabilities.process_strict import (
    ProcessSpawn,
    ProcessRefusal,
    ProcessError,
    ProcessConfig,
)

from backend.core.capabilities.screen_strict import (
    ScreenCapture,
    ScreenRefusal,
    ScreenError,
    ScreenConfig,
)

from backend.core.capabilities.network_strict import (
    NetworkFetch,
    NetworkRefusal,
    NetworkError,
    NetworkConfig,
)


class TestFilesystemRefusals:
    """Test filesystem refusals - prove impossible operations"""

    def test_relative_path_forbidden(self):
        """Relative paths are forbidden"""
        with pytest.raises(FilesystemError) as exc_info:
            FilesystemRead.execute({"path": "relative/path.txt"})
        assert exc_info.value.refusal == FilesystemRefusal.PATH_NOT_EXPLICIT

    def test_empty_path_forbidden(self):
        """Empty path is forbidden"""
        with pytest.raises(FilesystemError) as exc_info:
            FilesystemRead.execute({"path": ""})
        assert exc_info.value.refusal == FilesystemRefusal.PATH_NOT_EXPLICIT

    def test_symlink_forbidden(self):
        """Symlinks are forbidden"""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "target.txt"
            target.write_text("content")
            symlink = Path(tmpdir) / "link.txt"
            symlink.symlink_to(target)

            config = FilesystemConfig(
                allowed_directories={tmpdir},
                forbid_symlinks=True,
            )

            with pytest.raises(FilesystemError) as exc_info:
                FilesystemRead.execute({"path": str(symlink)}, config)
            assert exc_info.value.refusal == FilesystemRefusal.PATH_IS_SYMLINK

    def test_directory_read_forbidden(self):
        """Cannot read directory as file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FilesystemError) as exc_info:
                FilesystemRead.execute({"path": tmpdir})
            assert exc_info.value.refusal == FilesystemRefusal.IS_DIRECTORY

    def test_path_out_of_scope_forbidden(self):
        """Paths outside allowed directories are forbidden"""
        config = FilesystemConfig(
            allowed_directories={"/safe/directory"},
        )

        with pytest.raises(FilesystemError) as exc_info:
            FilesystemRead.execute({"path": "/unsafe/path.txt"}, config)
        assert exc_info.value.refusal == FilesystemRefusal.PATH_OUT_OF_SCOPE

    def test_write_without_content_forbidden(self):
        """Write without content field is forbidden"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FilesystemError) as exc_info:
                FilesystemWrite.execute({"path": f"{tmpdir}/file.txt"})
            assert exc_info.value.refusal == FilesystemRefusal.PATH_NOT_EXPLICIT

    def test_oversized_content_forbidden(self):
        """Content larger than max size is forbidden"""
        config = FilesystemConfig(max_file_size=100)
        large_content = "x" * 200

        with pytest.raises(FilesystemError) as exc_info:
            FilesystemWrite.execute(
                {"path": "/tmp/file.txt", "content": large_content},
                config,
            )
        assert exc_info.value.refusal == FilesystemRefusal.FILE_TOO_LARGE

    def test_directory_delete_forbidden(self):
        """Deleting directories (recursive) is forbidden"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FilesystemError) as exc_info:
                FilesystemDelete.execute({"path": tmpdir})
            assert exc_info.value.refusal == FilesystemRefusal.IS_DIRECTORY


class TestProcessRefusals:
    """Test process refusals - prove impossible operations"""

    def test_shell_invocation_forbidden(self):
        """Shell invocation is structurally forbidden"""
        config = ProcessConfig(
            allowed_executables={"python"},
            forbid_shell=True,
        )

        with pytest.raises(ProcessError) as exc_info:
            ProcessSpawn.execute({
                "executable": "/bin/sh",
                "args": ["-c", "malicious"],
            }, config)
        assert exc_info.value.refusal == ProcessRefusal.EXECUTABLE_NOT_ALLOWED

    def test_disallowed_executable_forbidden(self):
        """Disallowed executables are forbidden"""
        config = ProcessConfig(
            allowed_executables={"python"},
        )

        with pytest.raises(ProcessError) as exc_info:
            ProcessSpawn.execute({
                "executable": "/bin/rm",
                "args": ["-rf", "/"],
            }, config)
        assert exc_info.value.refusal == ProcessRefusal.EXECUTABLE_NOT_ALLOWED

    def test_timeout_exceeded_forbidden(self):
        """Timeout exceeding limit is forbidden"""
        config = ProcessConfig(max_timeout_seconds=10)

        with pytest.raises(ProcessError) as exc_info:
            ProcessSpawn.execute({
                "executable": "python",
                "args": [],
                "timeout": 60,
            }, config)
        assert exc_info.value.refusal == ProcessRefusal.TIMEOUT_EXCEEDED

    def test_missing_args_forbidden(self):
        """Missing args field is forbidden"""
        with pytest.raises(ProcessError) as exc_info:
            ProcessSpawn.execute({"executable": "python"})
        assert exc_info.value.refusal == ProcessRefusal.MISSING_ARGS

    def test_missing_executable_forbidden(self):
        """Missing executable field is forbidden"""
        with pytest.raises(ProcessError) as exc_info:
            ProcessSpawn.execute({"args": []})
        assert exc_info.value.refusal == ProcessRefusal.MISSING_EXECUTABLE


class TestScreenRefusals:
    """Test screen refusals - prove impossible operations"""

    def test_rate_limit_forbidden(self):
        """Excessive capture rate is forbidden"""
        config = ScreenConfig(min_rate_limit_ms=10000)

        context = {"region": (0, 0, 100, 100)}

        ScreenCapture.execute(context, config)

        with pytest.raises(ScreenError) as exc_info:
            ScreenCapture.execute(context, config)
        assert exc_info.value.refusal == ScreenRefusal.RATE_LIMIT_EXCEEDED

    def test_invalid_region_forbidden(self):
        """Invalid region dimensions are forbidden"""
        config = ScreenConfig(max_width=100, max_height=100)

        with pytest.raises(ScreenError) as exc_info:
            ScreenCapture.execute({"region": (0, 0, 200, 200)}, config)
        assert exc_info.value.refusal == ScreenRefusal.REGION_INVALID

    def test_unspecified_region_forbidden(self):
        """Unspecified region when full-screen disabled is forbidden"""
        config = ScreenConfig(allow_full_screen=False)

        with pytest.raises(ScreenError) as exc_info:
            ScreenCapture.execute({}, config)
        assert exc_info.value.refusal == ScreenRefusal.UNSPECIFIED_REGION


class TestNetworkRefusals:
    """Test network refusals - prove impossible operations"""

    def test_http_forbidden(self):
        """HTTP (non-HTTPS) is forbidden"""
        config = NetworkConfig(https_only=True)

        with pytest.raises(NetworkError) as exc_info:
            NetworkFetch.execute({
                "url": "http://example.com",
                "method": "GET",
            }, config)
        assert exc_info.value.refusal == NetworkRefusal.UNSAFE_SCHEME

    def test_disallowed_domain_forbidden(self):
        """Disallowed domains are forbidden"""
        config = NetworkConfig(
            allowed_domains={"trusted.com"},
        )

        with pytest.raises(NetworkError) as exc_info:
            NetworkFetch.execute({
                "url": "https://untrusted.com",
                "method": "GET",
            }, config)
        assert exc_info.value.refusal == NetworkRefusal.URL_NOT_ALLOWED

    def test_disallowed_method_forbidden(self):
        """Disallowed methods are forbidden"""
        config = NetworkConfig(
            allowed_methods={"GET", "POST"},
        )

        with pytest.raises(NetworkError) as exc_info:
            NetworkFetch.execute({
                "url": "https://trusted.com",
                "method": "DELETE",
            }, config)
        assert exc_info.value.refusal == NetworkRefusal.METHOD_NOT_ALLOWED

    def test_oversized_payload_forbidden(self):
        """Payload larger than max size is forbidden"""
        config = NetworkConfig(max_payload_bytes=100)
        large_payload = "x" * 200

        with pytest.raises(NetworkError) as exc_info:
            NetworkFetch.execute({
                "url": "https://trusted.com",
                "method": "POST",
                "body": large_payload,
            }, config)
        assert exc_info.value.refusal == NetworkRefusal.PAYLOAD_TOO_LARGE

    def test_missing_url_forbidden(self):
        """Missing URL field is forbidden"""
        with pytest.raises(NetworkError) as exc_info:
            NetworkFetch.execute({"method": "GET"})
        assert exc_info.value.refusal == NetworkRefusal.MISSING_URL


class TestNoCrossCapabilityCalls:
    """Test that capabilities cannot call each other"""

    def test_filesystem_cannot_call_process(self):
        """Filesystem cannot spawn processes"""
        with pytest.raises(Exception):
            FilesystemRead.execute({"path": "$(rm -rf /)"})

    def test_process_cannot_write_filesystem(self):
        """Process cannot write to arbitrary filesystem"""
        config = ProcessConfig(
            allowed_executables={"python"},
        )

        result = ProcessSpawn.execute({
            "executable": "python",
            "args": ["-c", "open('/etc/passwd', 'w')"],
        }, config)

        assert result["returncode"] != 0

    def test_network_cannot_spawn_process(self):
        """Network cannot spawn processes"""
        config = NetworkConfig(
            allowed_domains={"test.com"},
        )

        with pytest.raises(NetworkError) as exc_info:
            NetworkFetch.execute({
                "url": "https://test.com",
                "method": "GET",
                "body": "$(malicious)",
            }, config)


class TestNoRetries:
    """Test that retries are structurally impossible"""

    def test_filesystem_failure_is_terminal(self):
        """Filesystem failure cannot be retried by capability"""
        with pytest.raises(FilesystemError):
            FilesystemRead.execute({"path": "/nonexistent/file.txt"})

    def test_process_failure_is_terminal(self):
        """Process failure cannot be retried by capability"""
        with pytest.raises(ProcessError):
            ProcessSpawn.execute({
                "executable": "nonexistent",
                "args": [],
            })

    def test_network_failure_is_terminal(self):
        """Network failure cannot be retried by capability"""
        with pytest.raises(NetworkError):
            NetworkFetch.execute({
                "url": "https://invalid-domain-999999.com",
                "method": "GET",
            })


class TestNoDefaultsOrInference:
    """Test that no defaults or inference exist"""

    def test_no_default_filesystem_path(self):
        """Filesystem has no default path"""
        with pytest.raises(FilesystemError):
            FilesystemRead.execute({})

    def test_no_default_process_executable(self):
        """Process has no default executable"""
        with pytest.raises(ProcessError):
            ProcessSpawn.execute({})

    def test_no_default_network_url(self):
        """Network has no default URL"""
        with pytest.raises(NetworkError):
            NetworkFetch.execute({})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
