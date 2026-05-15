"""
Lokale Bewertungs-Engine für Claude Code Outputs.
Kein API-Key nötig. Analysiert Task, Output und Filesystem.
"""

import os
import re
from dataclasses import dataclass, field


# ─── FEHLERMUSTER (200+) ──────────────────────────────────────────────────────

ERROR_PATTERNS = [

    # ── Python: Syntax & Struktur ──────────────────────────────────────────────
    (r"Traceback \(most recent call last\)", "python_traceback", 10),
    (r"SyntaxError:", "python_syntax", 10),
    (r"IndentationError:", "python_indent", 10),
    (r"TabError:", "python_tab", 9),
    (r"unexpected EOF while parsing", "python_eof", 9),
    (r"invalid syntax", "python_invalid_syntax", 9),
    (r"EOFError:", "python_eof_error", 8),
    (r"unexpected indent", "python_unexpected_indent", 8),

    # ── Python: Laufzeitfehler ─────────────────────────────────────────────────
    (r"NameError:", "python_name", 8),
    (r"TypeError:", "python_type", 8),
    (r"ValueError:", "python_value", 8),
    (r"AttributeError:", "python_attr", 8),
    (r"ImportError:", "python_import", 9),
    (r"ModuleNotFoundError:", "python_module", 9),
    (r"KeyError:", "python_key", 7),
    (r"IndexError:", "python_index", 7),
    (r"ZeroDivisionError:", "python_zerodiv", 7),
    (r"RecursionError:", "python_recursion", 8),
    (r"OverflowError:", "python_overflow", 7),
    (r"MemoryError:", "python_memory", 8),
    (r"RuntimeError:", "python_runtime", 8),
    (r"StopIteration:", "python_stop_iter", 6),
    (r"GeneratorExit:", "python_gen_exit", 5),
    (r"SystemExit:", "python_sys_exit", 6),
    (r"OSError:", "python_os", 8),
    (r"IOError:", "python_io", 7),
    (r"FileNotFoundError:", "python_file_not_found", 9),
    (r"FileExistsError:", "python_file_exists", 7),
    (r"PermissionError:", "python_permission", 8),
    (r"IsADirectoryError:", "python_is_dir", 7),
    (r"NotADirectoryError:", "python_not_dir", 7),
    (r"ConnectionError:", "python_connection", 8),
    (r"TimeoutError:", "python_timeout", 8),
    (r"UnicodeDecodeError:", "python_unicode_decode", 7),
    (r"UnicodeEncodeError:", "python_unicode_encode", 7),
    (r"UnicodeError:", "python_unicode", 7),
    (r"AssertionError:", "python_assert", 7),
    (r"NotImplementedError:", "python_not_impl", 7),
    (r"raise \w+Error", "python_raise", 7),
    (r"raise \w+Exception", "python_raise_exc", 7),

    # ── Python: Tests ──────────────────────────────────────────────────────────
    (r"FAILED \(errors=\d+\)", "pytest_failed", 10),
    (r"FAILED \(failures=\d+\)", "pytest_failures", 10),
    (r"\d+ failed", "pytest_n_failed", 9),
    (r"ERRORS?\s*$", "pytest_errors", 9),
    (r"AssertionError: assert", "pytest_assert", 9),
    (r"E\s+assert\s+", "pytest_e_assert", 8),
    (r"FAIL: test_", "unittest_fail", 9),
    (r"ERROR: test_", "unittest_error", 9),
    (r"Ran \d+ test.* FAILED", "unittest_failed", 10),

    # ── JavaScript / TypeScript ────────────────────────────────────────────────
    (r"ReferenceError:", "js_reference", 9),
    (r"TypeError: .{0,60}is not (a function|defined|an object)", "js_type", 9),
    (r"SyntaxError: Unexpected token", "js_syntax_token", 9),
    (r"SyntaxError: Unexpected end of input", "js_syntax_eof", 9),
    (r"SyntaxError: Invalid or unexpected token", "js_syntax_invalid", 9),
    (r"Cannot read propert(y|ies) .{0,30}of (null|undefined)", "js_null_access", 10),
    (r"Cannot set propert(y|ies) .{0,30}of (null|undefined)", "js_null_set", 10),
    (r"is not defined", "js_not_defined", 8),
    (r"Uncaught (Error|TypeError|ReferenceError|RangeError)", "js_uncaught", 9),
    (r"UnhandledPromiseRejection", "js_promise_reject", 9),
    (r"Error: Cannot find module", "node_module_missing", 10),
    (r"Module not found: Error:", "webpack_module", 9),
    (r"Cannot resolve module", "js_resolve", 8),
    (r"RangeError:", "js_range", 8),
    (r"EvalError:", "js_eval", 7),
    (r"\[ERR_MODULE_NOT_FOUND\]", "node_esm", 9),
    (r"\[ERR_REQUIRE_ESM\]", "node_require_esm", 8),
    (r"Maximum call stack size exceeded", "js_stack_overflow", 9),

    # ── TypeScript ─────────────────────────────────────────────────────────────
    (r"error TS\d+:", "ts_error", 9),
    (r"TS\d+: Type .{0,60}is not assignable", "ts_type_assign", 9),
    (r"TS\d+: Property .{0,60}does not exist", "ts_prop_missing", 9),
    (r"TS\d+: Cannot find module", "ts_module", 9),
    (r"TS\d+: Argument of type", "ts_arg_type", 8),
    (r"TS\d+: Object is possibly (null|undefined)", "ts_nullable", 9),
    (r"TS\d+: Expected \d+ arguments", "ts_arg_count", 8),
    (r"TS\d+: Cannot find name", "ts_name", 8),
    (r"tsc: error", "ts_compiler", 9),

    # ── Node.js / npm / yarn / pnpm ────────────────────────────────────────────
    (r"npm ERR!", "npm_error", 9),
    (r"npm WARN.*ERESOLVE", "npm_conflict", 8),
    (r"npm ERR! code (ENOENT|EACCES|EPERM)", "npm_fs_error", 9),
    (r"npm ERR! 404", "npm_404", 8),
    (r"yarn error", "yarn_error", 9),
    (r"error Command failed with exit code", "yarn_exit_code", 8),
    (r"pnpm ERR!", "pnpm_error", 9),
    (r"ERESOLVE unable to resolve dependency", "npm_resolve", 8),
    (r"peer dep missing:", "npm_peer", 7),
    (r"Unmet peer dependency", "npm_unmet_peer", 7),

    # ── Shell / Bash / Zsh ─────────────────────────────────────────────────────
    (r"command not found", "shell_not_found", 9),
    (r"bash:.*: command not found", "bash_not_found", 9),
    (r"zsh:.*: command not found", "zsh_not_found", 9),
    (r"Permission denied", "permission_denied", 9),
    (r"No such file or directory", "no_such_file", 8),
    (r"Operation not permitted", "op_not_permitted", 8),
    (r"Disk quota exceeded", "disk_quota", 9),
    (r"Too many open files", "too_many_files", 7),
    (r"Argument list too long", "arg_too_long", 7),
    (r"exit code: [1-9]\d*", "nonzero_exit", 6),
    (r"exit status [1-9]", "nonzero_status", 6),
    (r"killed by signal", "signal_kill", 9),
    (r"Segmentation fault", "segfault", 10),
    (r"Bus error", "bus_error", 9),
    (r"Aborted \(core dumped\)", "core_dump", 10),

    # ── Node FS ────────────────────────────────────────────────────────────────
    (r"ENOENT:", "enoent", 9),
    (r"EACCES:", "eacces", 9),
    (r"EPERM:", "eperm", 8),
    (r"EEXIST:", "eexist", 7),
    (r"EISDIR:", "eisdir", 7),
    (r"ENOTDIR:", "enotdir", 7),
    (r"ENOTEMPTY:", "enotempty", 7),
    (r"ECONNREFUSED:", "econnrefused", 8),
    (r"ECONNRESET:", "econnreset", 7),
    (r"ETIMEDOUT:", "etimedout", 8),
    (r"EADDRINUSE:", "eaddrinuse", 8),

    # ── Build / Compiler ───────────────────────────────────────────────────────
    (r"Build failed", "build_failed", 10),
    (r"Build error", "build_error", 10),
    (r"Compilation failed", "compilation_failed", 10),
    (r"Compile error", "compile_error", 10),
    (r"make\[?\d?\]?: \*\*\* \[", "make_error", 9),
    (r"CMake Error", "cmake_error", 9),
    (r"ninja: error:", "ninja_error", 9),
    (r"ld: error:", "linker_error", 9),
    (r"undefined reference to", "linker_undef", 9),
    (r"multiple definition of", "linker_multiple", 8),

    # ── Rust ───────────────────────────────────────────────────────────────────
    (r"error\[E\d+\]", "rust_error", 9),
    (r"error: aborting due to", "rust_abort", 10),
    (r"thread '.+' panicked at", "rust_panic", 10),
    (r"RUST_BACKTRACE", "rust_backtrace_hint", 6),
    (r"cannot borrow .{0,40}as mutable", "rust_borrow_mut", 9),
    (r"does not live long enough", "rust_lifetime", 9),
    (r"mismatched types", "rust_type_mismatch", 9),
    (r"use of moved value", "rust_move", 9),
    (r"unused import", "rust_unused_import", 4),

    # ── Go ─────────────────────────────────────────────────────────────────────
    (r"go: .*: no such", "go_no_such", 9),
    (r"undefined: ", "go_undefined", 9),
    (r"cannot use .{0,40}\(type .{0,40}\) as type", "go_type", 9),
    (r"goroutine \d+ \[", "go_goroutine_panic", 9),
    (r"panic:", "go_panic", 10),
    (r"declared but not used", "go_unused_var", 6),
    (r"imported and not used", "go_unused_import", 6),
    (r"too many arguments", "go_args", 8),
    (r"not enough arguments", "go_args_missing", 8),

    # ── Java ───────────────────────────────────────────────────────────────────
    (r"Exception in thread .main.", "java_main_exc", 10),
    (r"NullPointerException", "java_npe", 10),
    (r"ArrayIndexOutOfBoundsException", "java_array_oob", 9),
    (r"ClassNotFoundException", "java_class_not_found", 9),
    (r"ClassCastException", "java_class_cast", 8),
    (r"StackOverflowError", "java_stack_overflow", 9),
    (r"OutOfMemoryError", "java_oom", 9),
    (r"error: cannot find symbol", "java_symbol", 9),
    (r"error: ';' expected", "java_semicolon", 8),
    (r"BUILD FAILURE", "maven_build_fail", 10),
    (r"COMPILATION ERROR", "java_compilation", 10),
    (r"Test run: \d+, Failures: [1-9]", "junit_fail", 10),

    # ── C / C++ ────────────────────────────────────────────────────────────────
    (r"error: expected .{0,30}before", "c_expected", 9),
    (r"error: .{0,40}'.*' undeclared", "c_undeclared", 9),
    (r"warning: implicit declaration", "c_implicit", 6),
    (r"undefined behavior", "c_ub", 8),
    (r"double free or corruption", "c_double_free", 10),
    (r"heap-buffer-overflow", "c_heap_overflow", 10),
    (r"stack-buffer-overflow", "c_stack_overflow", 10),
    (r"AddressSanitizer", "asan_error", 9),

    # ── Ruby / Rails ───────────────────────────────────────────────────────────
    (r"NameError: uninitialized constant", "ruby_const", 9),
    (r"NoMethodError: undefined method", "ruby_method", 9),
    (r"LoadError: cannot load such file", "ruby_load", 9),
    (r"SyntaxError: .+syntax error", "ruby_syntax", 9),
    (r"ActiveRecord::", "rails_ar_error", 8),
    (r"Gem::LoadError", "ruby_gem", 8),
    (r"bundler: failed to load command", "bundler_fail", 9),
    (r"\d+ example.*, \d+ failure", "rspec_fail", 10),

    # ── PHP ────────────────────────────────────────────────────────────────────
    (r"Parse error: syntax error, unexpected", "php_syntax", 10),
    (r"Fatal error: Uncaught", "php_fatal", 10),
    (r"Fatal error: Call to undefined", "php_undef", 10),
    (r"Warning: .{0,60}on line \d+", "php_warning", 6),
    (r"PHP Fatal error:", "php_fatal2", 10),
    (r"composer\.json.*not found", "composer_missing", 8),

    # ── SQL / Database ─────────────────────────────────────────────────────────
    (r"syntax error at or near", "sql_syntax", 9),
    (r"ERROR: .{0,60}does not exist", "sql_not_exists", 9),
    (r"column .{0,40}does not exist", "sql_col_missing", 9),
    (r"relation .{0,40}does not exist", "sql_table_missing", 9),
    (r"duplicate key value violates", "sql_unique", 8),
    (r"foreign key constraint", "sql_fk", 8),
    (r"OperationalError:", "db_operational", 8),
    (r"IntegrityError:", "db_integrity", 8),
    (r"ProgrammingError:", "db_programming", 8),
    (r"MongoError:", "mongo_error", 8),
    (r"MongoServerError:", "mongo_server", 8),
    (r"Redis connection", "redis_conn", 7),

    # ── Docker / Container ─────────────────────────────────────────────────────
    (r"docker: Error", "docker_error", 9),
    (r"Cannot connect to the Docker daemon", "docker_daemon", 9),
    (r"Error response from daemon:", "docker_daemon_response", 8),
    (r"failed to build: ", "docker_build_fail", 9),
    (r"OCI runtime exec failed", "docker_oci", 8),
    (r"container .{0,40}not found", "docker_no_container", 8),
    (r"image .{0,40}not found", "docker_no_image", 8),
    (r"Error: No such image", "docker_no_image2", 8),

    # ── Git ────────────────────────────────────────────────────────────────────
    (r"CONFLICT \(", "git_conflict", 9),
    (r"fatal:", "git_fatal", 9),
    (r"error: failed to push", "git_push_fail", 9),
    (r"error: Your local changes", "git_local_changes", 8),
    (r"error: pathspec .{0,40}did not match", "git_pathspec", 8),
    (r"refusing to merge unrelated histories", "git_unrelated", 8),
    (r"not a git repository", "git_no_repo", 8),
    (r"rejected.*\(non-fast-forward\)", "git_non_ff", 8),
    (r"Authentication failed", "git_auth", 9),

    # ── HTTP / Network ─────────────────────────────────────────────────────────
    (r"HTTP Error 4\d\d", "http_4xx", 8),
    (r"HTTP Error 5\d\d", "http_5xx", 9),
    (r"404 Not Found", "http_404", 8),
    (r"403 Forbidden", "http_403", 8),
    (r"401 Unauthorized", "http_401", 8),
    (r"500 Internal Server Error", "http_500", 9),
    (r"Connection refused", "conn_refused", 8),
    (r"Connection timed out", "conn_timeout", 8),
    (r"Name or service not known", "dns_fail", 8),
    (r"Could not resolve host", "dns_resolve", 8),
    (r"SSL: CERTIFICATE_VERIFY_FAILED", "ssl_cert", 8),
    (r"requests\.exceptions\.", "requests_error", 8),
    (r"aiohttp\.(ClientError|ServerError)", "aiohttp_error", 8),
    (r"fetch\(.+\) failed", "fetch_fail", 8),
    (r"net::ERR_", "chrome_net_error", 7),

    # ── React / Vue / Angular / Frontend ──────────────────────────────────────
    (r"React Hook .{0,60}is called conditionally", "react_hook_cond", 9),
    (r"Warning: Each child in a list should have a unique .key.", "react_key_warning", 6),
    (r"Warning: Cannot update a component .{0,40}while rendering", "react_update_warn", 7),
    (r"\[Vue warn\]:", "vue_warn", 7),
    (r"ERROR in ./src", "webpack_error", 9),
    (r"HMR.*error", "hmr_error", 7),
    (r"INVALID.*configuration", "webpack_config", 8),

    # ── Linter ─────────────────────────────────────────────────────────────────
    (r"\d+ error.* \d+ warning", "eslint_errors", 7),
    (r"ESLint found too many warnings", "eslint_warnings", 6),
    (r"pylint.*error", "pylint_error", 7),
    (r"flake8.*E\d+", "flake8_error", 6),
    (r"mypy.*error:", "mypy_error", 7),

    # ── Cloud / CI ─────────────────────────────────────────────────────────────
    (r"Error: Access denied", "cloud_access", 9),
    (r"(The specified bucket|No such bucket)", "s3_bucket", 8),
    (r"An error occurred \(", "aws_error", 8),
    (r"gcloud.* ERROR:", "gcloud_error", 8),
    (r"azure.* Error:", "azure_error", 8),

    # ── Generic / Universal ────────────────────────────────────────────────────
    (r"\bERROR\b(?! handling| checking| boundary)", "generic_error", 6),
    (r"\bFAILED\b(?! to match)", "generic_failed", 6),
    (r"\bFATAL\b", "generic_fatal", 8),
    (r"\bPANIC\b", "generic_panic", 9),
    (r"\bCRASH(ED)?\b", "generic_crash", 9),
    (r"TIMEOUT:", "timeout", 8),
    (r"timed out", "timed_out", 7),
    (r"not found:\s", "not_found", 6),
    (r"\brefused\b", "refused", 6),
    (r"\bunauthorized\b", "unauthorized", 7),
    (r"\bforbidden\b", "forbidden", 7),
    (r"stack trace:", "stack_trace", 8),
    (r"core dumped", "core_dumped", 10),
    (r"killed\s*$", "process_killed", 8),
    (r"out of memory", "oom", 9),
    (r"disk full", "disk_full", 9),

    # ── Claude / LLM verwirrt / blockiert ─────────────────────────────────────
    (r"I('m| am) (unable|not able) to", "claude_unable", 5),
    (r"I (can't|cannot) (access|read|write|create|modify|execute|run)", "claude_cant", 5),
    (r"I don't (have|understand|know)", "claude_confused", 4),
    (r"Please (provide|clarify|specify|share|give)", "claude_needs_input", 5),
    (r"I need (more|additional) (information|context|details|clarification)", "claude_needs_info", 5),
    (r"could you (please )?(provide|clarify|share|tell me)", "claude_asks", 4),
    (r"I'm not sure (what|how|which|where)", "claude_unsure", 4),
    (r"I'll need you to", "claude_needs_you", 5),
    (r"as an AI (language model|assistant)", "claude_ai_disclaimer", 3),
    (r"I don't have (access|the ability|permission)", "claude_no_access", 6),
    (r"I cannot browse|I can't browse", "claude_no_browse", 4),
    (r"As of my (knowledge|training)", "claude_cutoff", 3),
    (r"I apologize, but I (can't|cannot|am unable)", "claude_apology_cant", 5),
]


# ─── ERFOLGSMUSTER (100+) ─────────────────────────────────────────────────────

SUCCESS_PATTERNS = [

    # ── Explizite Erfolgs-Aussagen ─────────────────────────────────────────────
    (r"(Successfully|Erfolgreich) (created|written|saved|installed|built|compiled|updated|configured|deployed|migrated|generated|executed|completed|finished|applied)", "explicit_success", 9),
    (r"(File|Files|Directory|Module|Package|Function|Class|Component|Service|App|Server|Database|Table|Schema|Route|Endpoint|Model|View|Controller|Migration|Fixture|Seed) (created|written|saved|installed|added|generated|built|updated|configured|deployed)", "artifact_created", 8),
    (r"(Done|Fertig|Complete[d]?|Finished|All (done|tasks complete|checks passed)|Abgeschlossen)[\.!\s]*$", "done_signal", 8),
    (r"(Everything (looks|is) (good|fine|correct|working|ok))", "everything_ok", 7),
    (r"(All (good|set|done|correct|working|clear))[\.!]?", "all_good", 7),
    (r"(Task|Aufgabe) (complete[d]?|erledigt|abgeschlossen|done|finished)", "task_done", 8),
    (r"(Implementation|Implementierung) (complete[d]?|done|finished|abgeschlossen)", "impl_done", 8),
    (r"(Changes|Änderungen) (applied|saved|written|committed|made)", "changes_applied", 7),
    (r"(Setup|Installation|Configuration) (complete[d]?|successful|done|finished)", "setup_done", 8),
    (r"(Successfully|Erfolgreich) (ran|executed|run)", "exec_success", 7),

    # ── Tests ─────────────────────────────────────────────────────────────────
    (r"All \d+ (tests?|specs?|checks?) (pass(ed)?|passing|green)", "all_tests_pass", 10),
    (r"Tests? (passed|passing|successful|all green)", "tests_pass", 9),
    (r"\d+ passed(, \d+ warnings?)?$", "pytest_passed", 9),
    (r"OK \(\d+ tests?\)", "unittest_ok", 9),
    (r"\d+ examples?, 0 failures", "rspec_pass", 9),
    (r"Test Suites: .* passed", "jest_suite_pass", 9),
    (r"Tests: .* passed", "jest_test_pass", 8),
    (r"PASS src/", "jest_pass", 8),
    (r"\d+ specs?, 0 failures", "jasmine_pass", 9),
    (r"✓ \d+ (tests?|specs?|assertions?)", "checkmark_tests", 8),
    (r"(0 errors?|no errors?|error-free|fehlerlos)", "zero_errors", 9),
    (r"(0 failures?|no failures?)", "zero_failures", 9),
    (r"(0 warnings?|no warnings?)", "zero_warnings", 7),

    # ── Pakete & Dependencies ──────────────────────────────────────────────────
    (r"(npm|pip|pip3|brew|cargo|go get|gem|composer|apt|apt-get|yarn|pnpm).{0,40}(installed|added|success|done|complete)", "package_installed", 8),
    (r"added \d+ packages?", "npm_added", 8),
    (r"Successfully installed .+", "pip_installed", 8),
    (r"installing .{0,40}\.\.\. done", "brew_done", 8),
    (r"Resolving dependencies\.\.\.done", "composer_done", 8),
    (r"Compiling.+\([\d\.]+\)", "cargo_compiling", 6),
    (r"Finished .* in .+s", "cargo_finished", 8),

    # ── Build & Compile ────────────────────────────────────────────────────────
    (r"(Build|Compilation) (success(ful)?|complete[d]?|finished|passed)", "build_success", 10),
    (r"webpack compiled successfully", "webpack_success", 10),
    (r"compiled (successfully|with no errors?)", "compiled_ok", 10),
    (r"bundle\.js \d+(\.\d+)? (KiB|MiB|bytes?)", "webpack_bundle", 7),
    (r"(BUILD SUCCESS|BUILD PASSED)", "build_success_caps", 10),
    (r"Successfully compiled TypeScript", "ts_compiled", 9),
    (r"tsc: compile success", "tsc_success", 9),
    (r"vite built in \d+ms", "vite_success", 8),
    (r"next build.*successful", "next_build", 8),
    (r"gatsby build.*complete", "gatsby_build", 8),

    # ── Server & Services ──────────────────────────────────────────────────────
    (r"(Server|App|Service|API|Flask|Express|FastAPI|Django|Rails) (running|started|listening|ready).{0,40}(:\d+|port \d+)", "server_started", 8),
    (r"Listening on (port|:\s?)\d+", "listening_port", 8),
    (r"ready on (http|https)://", "ready_on_url", 8),
    (r"started successfully on port \d+", "started_port", 8),
    (r"running at http://", "running_at", 8),
    (r"Local:.*http://localhost", "local_dev", 7),
    (r"✓ Ready in \d+ms", "next_ready", 8),

    # ── Git ────────────────────────────────────────────────────────────────────
    (r"\[.+\] .{3,80}", "git_commit", 7),
    (r"(1 file|[\d]+ files?) (changed|inserted|deleted)", "git_changes", 7),
    (r"committed|commit created", "committed", 7),
    (r"(Pushed|push.{0,10}origin)", "pushed", 7),
    (r"Branch .{3,40}(created|set up)", "branch_created", 7),
    (r"Merge (made|complete[d]?)", "merge_done", 7),
    (r"Already up to date", "git_up_to_date", 6),
    (r"Fast-forward", "git_ff", 6),

    # ── Datenbank ─────────────────────────────────────────────────────────────
    (r"Migration(s?) (ran|applied|complete[d]?|done|successful)", "migration_done", 9),
    (r"(Table|Schema|Database|Collection|Index) (created|applied|built|migrated)", "db_created", 8),
    (r"\d+ row(s?) (inserted|updated|deleted|affected)", "db_rows", 7),
    (r"(Seed|Seeded|Seeding) (complete[d]?|done|successful)", "seed_done", 7),
    (r"(Connected|Connection established) to (database|db|postgres|mysql|mongo|redis)", "db_connected", 7),

    # ── Docker / Deploy ───────────────────────────────────────────────────────
    (r"Successfully (built|tagged|pushed) .{0,40}", "docker_success", 8),
    (r"(Image|Container) (created|started|running|built)", "docker_running", 7),
    (r"Deploying to .{3,40}(done|complete[d]?|success)", "deploy_done", 8),
    (r"(Deployment|Release) (complete[d]?|successful|done)", "deployment_done", 9),
    (r"Live at (http|https)://", "live_at", 9),

    # ── Datei-Operationen ─────────────────────────────────────────────────────
    (r"(Created|Wrote|Saved|Updated|Modified|Generated|Copied|Moved) (file|files|\.py|\.js|\.ts|\.html|\.css|\.json|\.md)", "file_written", 7),
    (r"(File|Files) (saved|written|created|updated)", "file_saved", 7),
    (r"(Writing|Generating|Creating) .*\.\w+", "file_generating", 5),
    (r"output (written to|saved to|at) ", "output_written", 7),

    # ── Visuelle Signale ──────────────────────────────────────────────────────
    (r"(✓|✅|☑|✔)\s?.{0,40}", "checkmark", 6),
    (r"(🎉|🚀|✨|🎊|💯)\s", "success_emoji", 5),
    (r"(PASS(ED)?|OK|SUCCESS|DONE)\s*$", "caps_success", 7),
    (r"(green|bestanden|erfolgreich)\s*$", "green_signal", 6),
]


# ─── TASK-TYPEN (80+) ────────────────────────────────────────────────────────

TASK_PATTERNS = [
    # Deutsch — Erstellen
    (r"erstell[e]?\s+(?:eine?\s+)?(.+?\.\w+)", "create_file"),
    (r"erstell[e]?\s+(?:eine?\s+)?([\w\s]+(?:klasse|funktion|modul|skript|seite|api|server|datenbank|tabelle|component|service))", "create_thing_de"),
    (r"schreib[e]?\s+(?:eine?\s+)?(.+)", "write_de"),
    (r"generier[e]?\s+(?:eine?\s+)?(.+)", "generate_de"),
    (r"bau[e]?\s+(?:eine?\s+)?(.+)", "build_de"),
    (r"setz[e]?\s+.{0,20}auf", "setup_de"),
    (r"richte?\s+.{0,20}ein", "setup_de2"),
    (r"füge?\s+(.+)\s+hinzu", "add_de"),
    (r"implementier[e]?\s+(.+)", "implement_de"),
    (r"programmier[e]?\s+(.+)", "code_de"),
    (r"entwickl[e]?\s+(.+)", "develop_de"),
    (r"fixi?\s+(?:den?\s+)?(.+)", "fix_de"),
    (r"beheb[e]?\s+(.+)", "fix_de2"),
    (r"reparier[e]?\s+(.+)", "fix_de3"),
    (r"korrigier[e]?\s+(.+)", "fix_de4"),
    (r"optimier[e]?\s+(.+)", "optimize_de"),
    (r"verbessere?\s+(.+)", "improve_de"),
    (r"refaktorier[e]?\s+(.+)", "refactor_de"),
    (r"umschreib[e]?\s+(.+)", "refactor_de2"),
    (r"bereinig[e]?\s+(.+)", "clean_de"),
    (r"installier[e]?\s+(.+)", "install_de"),
    (r"aktualisier[e]?\s+(.+)", "update_de"),
    (r"konvertier[e]?\s+(.+)", "convert_de"),
    (r"migrier[e]?\s+(.+)", "migrate_de"),
    (r"teste?\s+(.+)", "test_de"),
    (r"deploy[e]?\s+(.+)", "deploy_de"),
    (r"lösch[e]?\s+(.+)", "delete_de"),
    (r"entfern[e]?\s+(.+)", "remove_de"),
    (r"dokumentier[e]?\s+(.+)", "document_de"),
    (r"konfiguriert?\s+(.+)", "configure_de"),

    # Englisch — Create / Build
    (r"create\s+(?:a\s+)?(.+?\.\w+)", "create_file"),
    (r"create\s+(?:a\s+)?([\w\s]+(class|function|module|script|page|api|server|database|table|component|service|hook|middleware|route|endpoint))", "create_thing"),
    (r"write\s+(?:a\s+)?(.+)", "write"),
    (r"generate\s+(?:a\s+)?(.+)", "generate"),
    (r"build\s+(?:a\s+)?(.+)", "build"),
    (r"make\s+(?:a\s+)?(.+)", "make"),
    (r"implement\s+(?:a\s+)?(.+)", "implement"),
    (r"develop\s+(?:a\s+)?(.+)", "develop"),
    (r"code\s+(?:a\s+)?(.+)", "code"),
    (r"scaffold\s+(.+)", "scaffold"),
    (r"set\s+up\s+(.+)", "setup"),
    (r"initialize\s+(.+)", "initialize"),
    (r"bootstrap\s+(.+)", "bootstrap"),
    (r"configure\s+(.+)", "configure"),
    (r"setup\s+(.+)", "setup2"),

    # Englisch — Fix / Debug
    (r"fix\s+(?:the\s+)?(.+)", "fix"),
    (r"debug\s+(.+)", "debug"),
    (r"resolve\s+(.+)", "resolve"),
    (r"solve\s+(.+)", "solve"),
    (r"repair\s+(.+)", "repair"),
    (r"patch\s+(.+)", "patch"),
    (r"correct\s+(.+)", "correct"),
    (r"handle\s+(?:the\s+)?(.+)\s+error", "handle_error"),

    # Englisch — Modify
    (r"add\s+(?:a\s+)?(.+)", "add"),
    (r"update\s+(.+)", "update"),
    (r"modify\s+(.+)", "modify"),
    (r"change\s+(.+)", "change"),
    (r"edit\s+(.+)", "edit"),
    (r"extend\s+(.+)", "extend"),
    (r"enhance\s+(.+)", "enhance"),
    (r"improve\s+(.+)", "improve"),
    (r"optimize\s+(.+)", "optimize"),
    (r"refactor\s+(.+)", "refactor"),
    (r"restructure\s+(.+)", "restructure"),
    (r"reorganize\s+(.+)", "reorganize"),
    (r"clean\s*up\s+(.+)", "cleanup"),

    # Englisch — Test / Quality
    (r"(write\s+)?(a\s+)?test(s)?\s+(for|of)\s+(.+)", "write_test"),
    (r"test\s+(.+)", "test"),
    (r"spec\s+(.+)", "spec"),
    (r"lint\s+(.+)", "lint"),
    (r"format\s+(.+)", "format"),
    (r"type.?check\s+(.+)", "typecheck"),

    # Englisch — Deploy / Infra
    (r"deploy\s+(.+)", "deploy"),
    (r"publish\s+(.+)", "publish"),
    (r"release\s+(.+)", "release"),
    (r"migrate\s+(.+)", "migrate"),
    (r"install\s+(.+)", "install"),
    (r"uninstall\s+(.+)", "uninstall"),
    (r"upgrade\s+(.+)", "upgrade"),
    (r"downgrade\s+(.+)", "downgrade"),

    # Englisch — Analysis / Docs
    (r"document\s+(.+)", "document"),
    (r"explain\s+(.+)", "explain"),
    (r"analyze\s+(.+)", "analyze"),
    (r"review\s+(.+)", "review"),
    (r"audit\s+(.+)", "audit"),
    (r"delete\s+(?:the\s+)?(.+)", "delete"),
    (r"remove\s+(?:the\s+)?(.+)", "remove"),
    (r"convert\s+(.+)", "convert"),
    (r"parse\s+(.+)", "parse"),
    (r"import\s+(.+)\s+from", "import_from"),
]


# ─── DATEITYPEN (100+) ────────────────────────────────────────────────────────

FILE_EXTENSIONS = {
    # Python
    ".py": "Python", ".pyw": "Python", ".pyi": "Python Stub",
    ".pyc": "Python Bytecode", ".pyd": "Python Extension",
    # JavaScript
    ".js": "JavaScript", ".mjs": "JavaScript ESM", ".cjs": "CommonJS",
    ".jsx": "React JSX", ".ts": "TypeScript", ".tsx": "React TSX",
    ".d.ts": "TypeScript Declaration",
    # Web
    ".html": "HTML", ".htm": "HTML", ".xhtml": "XHTML",
    ".css": "CSS", ".scss": "SCSS", ".sass": "SASS", ".less": "LESS",
    ".svg": "SVG", ".vue": "Vue", ".svelte": "Svelte",
    # Data
    ".json": "JSON", ".jsonc": "JSON with Comments",
    ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML", ".ini": "INI", ".cfg": "Config",
    ".env": "Env File", ".xml": "XML", ".csv": "CSV",
    ".tsv": "TSV", ".parquet": "Parquet", ".avro": "Avro",
    # Documentation
    ".md": "Markdown", ".mdx": "MDX", ".rst": "reStructuredText",
    ".txt": "Text", ".tex": "LaTeX",
    # Shell
    ".sh": "Shell", ".bash": "Bash", ".zsh": "Zsh",
    ".fish": "Fish", ".ps1": "PowerShell", ".bat": "Batch",
    ".cmd": "CMD",
    # Backend
    ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".kt": "Kotlin", ".scala": "Scala", ".groovy": "Groovy",
    ".cs": "C#", ".fs": "F#", ".vb": "VB.NET",
    ".c": "C", ".cpp": "C++", ".cc": "C++", ".cxx": "C++",
    ".h": "C Header", ".hpp": "C++ Header",
    ".rb": "Ruby", ".erb": "ERB", ".rake": "Rake",
    ".php": "PHP", ".phtml": "PHP HTML",
    ".swift": "Swift", ".m": "Objective-C",
    ".r": "R", ".R": "R",
    ".jl": "Julia", ".hs": "Haskell", ".ex": "Elixir",
    ".exs": "Elixir Script", ".erl": "Erlang",
    ".lua": "Lua", ".pl": "Perl", ".pm": "Perl Module",
    ".dart": "Dart",
    # Database
    ".sql": "SQL", ".psql": "PostgreSQL", ".sqlite": "SQLite",
    ".prisma": "Prisma Schema", ".graphql": "GraphQL", ".gql": "GraphQL",
    # Config / Build
    ".dockerfile": "Dockerfile", ".containerfile": "Containerfile",
    ".tf": "Terraform", ".tfvars": "Terraform Vars",
    ".hcl": "HCL",
    ".gradle": "Gradle", ".maven": "Maven",
    ".makefile": "Makefile", ".mk": "Makefile",
    ".cmake": "CMake",
    ".lock": "Lock File", ".sum": "Go Sum",
    # Notebooks
    ".ipynb": "Jupyter Notebook",
    # Other
    ".proto": "Protobuf", ".thrift": "Thrift",
    ".wasm": "WebAssembly", ".wat": "WAT",
}


# ─── FEHLER-RATSCHLÄGE (100+) ────────────────────────────────────────────────

ERROR_ADVICE = {
    # Python
    "python_traceback": "Lese den Traceback von unten nach oben — die letzte Zeile zeigt den eigentlichen Fehler.",
    "python_syntax": "Prüfe Einrückungen, fehlende Doppelpunkte, ungültige Zeichen. Zeile im Fehler beachten.",
    "python_indent": "Konsistente Einrückung verwenden — nur Spaces oder nur Tabs, nie gemischt.",
    "python_module": "Führe erst 'pip install <paket>' aus. In venv? Dann 'source venv/bin/activate'.",
    "python_import": "Prüfe Modulname und Import-Pfad. Ist __init__.py vorhanden bei eigenen Paketen?",
    "python_name": "Variable nicht definiert. Prüfe Schreibweise und ob sie vor der Verwendung definiert ist.",
    "python_type": "Falscher Datentyp. Prüfe was die Funktion erwartet (str, int, list, dict).",
    "python_value": "Ungültiger Wert. Prüfe Eingabe-Validierung und erlaubte Wertebereiche.",
    "python_attr": "Objekt hat kein solches Attribut. Prüfe Klasse und ob Methode existiert.",
    "python_key": "Key existiert nicht im Dictionary. Nutze .get() oder prüfe erst mit 'if key in dict'.",
    "python_index": "Index außerhalb der Listengrenzen. Prüfe Länge mit len() vor dem Zugriff.",
    "python_file_not_found": "Datei nicht gefunden. Prüfe Pfad, Arbeitsverzeichnis und ob Datei existiert.",
    "python_permission": "Keine Schreibrechte. Prüfe Verzeichnis-Permissions oder wähle anderen Pfad.",
    "python_recursion": "Stack overflow durch zu tiefe Rekursion. Füge Abbruchbedingung hinzu oder erhöhe sys.setrecursionlimit.",
    "python_timeout": "Zeitlimit überschritten. Optimiere langsame Operationen oder erhöhe den Timeout.",
    "pytest_failed": "Tests fehlgeschlagen. Lese die Fehlermeldungen und korrigiere den Code entsprechend.",
    "pytest_assert": "Assert-Fehler: Erwarteter und tatsächlicher Wert stimmen nicht überein.",
    # JavaScript
    "js_reference": "Variable ist nicht definiert. Prüfe Import, Schreibweise und Scope.",
    "js_type": "Falsche Verwendung: undefiniert, null oder falscher Typ. Prüfe ob Objekt initialisiert ist.",
    "js_syntax_token": "Syntaxfehler: Unerwartetes Token. Prüfe fehlende Klammern, Kommas oder Semikolons.",
    "js_null_access": "Zugriff auf Property von null/undefined. Prüfe ob Objekt existiert bevor du darauf zugreifst.",
    "js_promise_reject": "Unbehandelte Promise-Ablehnung. Füge .catch() oder try/catch mit await hinzu.",
    "js_stack_overflow": "Maximale Aufruftiefe überschritten. Prüfe auf endlose Rekursion.",
    "js_not_defined": "Variable nicht definiert. Prüfe Import-Anweisungen und Variablen-Deklaration.",
    # TypeScript
    "ts_error": "TypeScript-Compilerfehler. Prüfe Typen, Interfaces und Imports.",
    "ts_type_assign": "Typ ist nicht zuweisbar. Prüfe Interface-Definitionen und generische Typen.",
    "ts_prop_missing": "Property existiert nicht auf dem Typ. Erweitere das Interface oder prüfe den Typ.",
    "ts_nullable": "Objekt ist möglicherweise null/undefined. Nutze optionalen Chaining (?.) oder Null-Check.",
    "ts_module": "TypeScript kann Modul nicht finden. Prüfe @types/ Package und tsconfig paths.",
    "ts_compiler": "TypeScript-Kompilierung fehlgeschlagen. Führe 'tsc --noEmit' für Details aus.",
    # Node.js
    "node_module_missing": "Node-Modul nicht gefunden. Führe 'npm install' aus oder prüfe den Modulnamen.",
    "npm_error": "npm-Fehler. Prüfe package.json, führe 'npm install' aus oder lösche node_modules und reinstalliere.",
    "npm_resolve": "Abhängigkeitskonflikt. Nutze 'npm install --legacy-peer-deps' oder löse Konflikt manuell.",
    "npm_conflict": "Versionskonflikte in node_modules. Versuche 'npm dedupe' oder update Pakete.",
    "yarn_error": "Yarn-Fehler. Prüfe yarn.lock und führe 'yarn install --frozen-lockfile' aus.",
    "pnpm_error": "pnpm-Fehler. Prüfe pnpm-lock.yaml und führe 'pnpm install' aus.",
    "node_esm": "ES-Modul nicht gefunden. Prüfe Dateiendung (.mjs) und type in package.json.",
    "node_require_esm": "require() kann ESM nicht laden. Nutze dynamic import() oder konvertiere zu CommonJS.",
    # Shell
    "shell_not_found": "Befehl nicht gefunden. Prüfe ob das Tool installiert ist und ob es im PATH liegt.",
    "permission_denied": "Zugriff verweigert. Prüfe Dateirechte mit 'ls -la' und passe ggf. mit 'chmod' an.",
    "no_such_file": "Datei/Verzeichnis nicht vorhanden. Prüfe Pfad und Arbeitsverzeichnis mit 'pwd'.",
    "nonzero_exit": "Befehl fehlgeschlagen. Prüfe den letzten Exit-Code und analysiere die Fehlerausgabe.",
    "segfault": "Segmentation Fault: Speicherzugriffsverletzung. Prüfe Pointer, Array-Grenzen und Speicher.",
    # Build
    "build_failed": "Build fehlgeschlagen. Prüfe alle Abhängigkeiten, Konfiguration und Build-Logs.",
    "compilation_failed": "Kompilierung fehlgeschlagen. Behebe alle Compilerfehler und prüfe Syntax.",
    "make_error": "Make-Fehler. Prüfe das Makefile, Abhängigkeiten und ob alle Tools installiert sind.",
    "webpack_error": "Webpack-Fehler. Prüfe webpack.config.js, Imports und Module-Loader.",
    # Rust
    "rust_error": "Rust-Compilerfehler. Lese die Fehlermeldung genau — Rust erklärt oft die Lösung.",
    "rust_panic": "Rust-Panic. Prüfe unwrap()-Aufrufe und füge .expect() mit sinnvoller Nachricht hinzu.",
    "rust_borrow_mut": "Borrow-Checker: mutable borrow nicht möglich. Prüfe Ownership und Lifetimes.",
    "rust_lifetime": "Lifetime-Fehler. Prüfe ob Referenzen den richtigen Scope haben.",
    "rust_move": "Moved value: Wert wurde bereits konsumiert. Nutze .clone() oder Referenz.",
    # Go
    "go_panic": "Go-Panic. Prüfe auf nil-Pointer-Dereference und füge Nil-Checks hinzu.",
    "go_undefined": "Undefined symbol. Prüfe Package-Imports und ob Funktion/Variable exportiert ist.",
    "go_type": "Typ-Mismatch. Go ist streng typisiert — explizite Konvertierung nötig.",
    # Java
    "java_npe": "NullPointerException: Objekt ist null. Füge Null-Checks hinzu bevor du Methoden aufrufst.",
    "java_class_not_found": "Klasse nicht gefunden. Prüfe Classpath und ob Dependency in pom.xml/build.gradle.",
    "java_stack_overflow": "Stack Overflow: unendliche Rekursion. Prüfe Abbruchbedingungen.",
    "maven_build_fail": "Maven Build fehlgeschlagen. Führe 'mvn clean install -X' für Details aus.",
    # Database
    "sql_syntax": "SQL-Syntaxfehler. Prüfe SQL-Statement, Anführungszeichen und reservierte Wörter.",
    "sql_table_missing": "Tabelle nicht gefunden. Führe zuerst Migrationen aus ('python manage.py migrate').",
    "db_operational": "Datenbankverbindungsfehler. Prüfe Connection-String, Port und ob DB-Server läuft.",
    "db_integrity": "Integritätsfehler: Unique-Constraint oder Foreign-Key verletzt.",
    "mongo_error": "MongoDB-Fehler. Prüfe Connection-String und ob mongod-Service läuft.",
    "redis_conn": "Redis nicht erreichbar. Prüfe ob Redis läuft ('redis-cli ping').",
    # Docker
    "docker_daemon": "Docker-Daemon nicht erreichbar. Starte Docker Desktop oder 'sudo systemctl start docker'.",
    "docker_build_fail": "Docker-Build fehlgeschlagen. Prüfe Dockerfile und ob alle COPY-Quellen existieren.",
    "docker_no_image": "Docker-Image nicht gefunden. Führe 'docker pull <image>' oder 'docker build' aus.",
    # Git
    "git_conflict": "Merge-Konflikt. Löse Konflikte in den Dateien, dann 'git add .' und 'git commit'.",
    "git_fatal": "Kritischer Git-Fehler. Prüfe ob du in einem Git-Repository bist und ob die Remote erreichbar ist.",
    "git_push_fail": "Push abgelehnt. Führe zuerst 'git pull --rebase' aus um lokale und Remote-Änderungen zu mergen.",
    "git_auth": "Git-Authentifizierung fehlgeschlagen. Prüfe SSH-Key oder Access-Token.",
    "git_no_repo": "Kein Git-Repository. Führe 'git init' aus oder wechsle in das richtige Verzeichnis.",
    # HTTP
    "http_404": "Ressource nicht gefunden (404). Prüfe URL, Route-Definition und ob Server läuft.",
    "http_401": "Nicht authentifiziert (401). Prüfe API-Key, Token oder Login-Credentials.",
    "http_403": "Zugriff verweigert (403). Prüfe Permissions und Benutzer-Rolle.",
    "http_500": "Interner Serverfehler (500). Prüfe Server-Logs für den eigentlichen Fehler.",
    "conn_refused": "Verbindung abgelehnt. Prüfe ob der Ziel-Service läuft und auf dem richtigen Port hört.",
    "conn_timeout": "Verbindungs-Timeout. Prüfe Netzwerk, Firewall und ob der Service erreichbar ist.",
    "dns_resolve": "DNS-Auflösung fehlgeschlagen. Prüfe Hostname, Netzwerkverbindung und /etc/hosts.",
    # Frontend
    "react_hook_cond": "React-Hook wird bedingt aufgerufen. Hooks müssen immer in der gleichen Reihenfolge aufgerufen werden.",
    "webpack_module": "Webpack kann Modul nicht auflösen. Prüfe Alias-Config in webpack.config.js.",
    # Claude
    "claude_unable": "Claude ist blockiert. Formuliere den Task als lokale Operation ohne externe Zugriffe.",
    "claude_cant": "Claude verweigert Zugriff. Stelle sicher dass Pfade existieren und nutze absolute Pfade.",
    "claude_needs_input": "Claude fragt nach mehr Info. Ergänze den Task mit konkreten Details und Defaults.",
    "claude_confused": "Claude ist unsicher. Formuliere den Task klarer mit explizitem erwarteten Ergebnis.",
    "claude_no_access": "Claude hat keinen Zugriff. Übergebe den Inhalt direkt im Prompt statt auf Dateien zu verweisen.",
    # Generic
    "generic_error": "Prüfe die vollständige Fehlermeldung und behebe die Ursache systematisch.",
    "generic_failed": "Vorgang fehlgeschlagen. Prüfe Logs und führe den Schritt manuell aus.",
    "oom": "Out of Memory. Optimiere Speicherverbrauch oder erhöhe verfügbaren RAM.",
    "timeout": "Timeout überschritten. Optimiere langsame Operationen oder erhöhe den Timeout-Wert.",
    "enoent": "Datei/Verzeichnis nicht gefunden (ENOENT). Prüfe Pfad und ob Datei existiert.",
    "eacces": "Zugriff verweigert (EACCES). Prüfe Dateirechte.",
    "eaddrinuse": "Port bereits belegt. Stoppe den anderen Prozess oder nutze einen anderen Port.",
}


# ─── STOPWÖRTER ───────────────────────────────────────────────────────────────

STOPWORDS = {
    # Deutsch
    "eine", "einen", "einer", "einem", "eines", "der", "die", "das",
    "den", "dem", "des", "und", "oder", "aber", "auch", "noch", "schon",
    "mit", "ohne", "für", "über", "unter", "nach", "vor", "bei", "seit",
    "durch", "gegen", "zwischen", "neben", "hinter", "auf", "an", "in",
    "dass", "wenn", "dann", "also", "damit", "weil", "denn", "aber",
    "erstelle", "schreibe", "baue", "mache", "füge", "hinzu", "nutze",
    "verwende", "benutze", "implementiere", "entwickle", "programmiere",
    "teste", "prüfe", "deploye", "installiere", "konfiguriere",
    # Englisch
    "the", "a", "an", "and", "or", "but", "with", "without", "for",
    "from", "to", "in", "on", "at", "by", "of", "as", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "can", "shall", "that", "this", "these", "those", "which",
    "who", "what", "where", "when", "how", "why",
    "create", "write", "build", "make", "add", "use", "implement",
    "develop", "program", "generate", "setup", "configure", "deploy",
    "install", "test", "fix", "update", "modify", "change",
    "file", "files", "folder", "directory", "code", "script",
    # Technisch (zu generisch)
    "function", "class", "module", "method", "variable", "value",
    "data", "object", "array", "list", "string", "number", "type",
    "new", "old", "simple", "basic", "small", "large", "main",
}


@dataclass
class EvalResult:
    status: str
    confidence: int
    grund: str
    details: list[str] = field(default_factory=list)
    verbesserungs_prompt: str = ""

    def to_dict(self) -> dict:
        d = {
            "status": self.status,
            "confidence": self.confidence,
            "grund": self.grund,
        }
        if self.verbesserungs_prompt:
            d["verbesserungs_prompt"] = self.verbesserungs_prompt
        return d


# ─── HAUPT-EVALUATOR ─────────────────────────────────────────────────────────

class LocalEvaluator:

    def evaluate(self, task: str, output: str, directory: str) -> EvalResult:
        task_info   = self._parse_task(task)
        error_hits  = self._find_errors(output)
        success_hits = self._find_successes(output)
        fs_result   = self._check_filesystem(task_info, directory)
        quality     = self._assess_output_quality(output)
        keyword_hit = self._check_keyword_coverage(task_info, output)

        error_score   = sum(w for _, _, w in error_hits)
        success_score = sum(w for _, _, w in success_hits)
        fs_bonus      = fs_result["bonus"]
        fs_penalty    = fs_result["penalty"]

        net = (success_score + fs_bonus + keyword_hit) - (error_score + fs_penalty) + quality["score"]

        details = []
        if error_hits:
            details.append(f"Fehler: {', '.join(n for _, n, _ in error_hits[:4])}")
        if success_hits:
            details.append(f"Erfolg: {', '.join(n for _, n, _ in success_hits[:4])}")
        if fs_result["found"]:
            details.append(f"Dateien gefunden: {', '.join(fs_result['found'])}")
        if fs_result["missing"]:
            details.append(f"Dateien fehlen: {', '.join(fs_result['missing'])}")
        if keyword_hit > 0:
            details.append(f"Keywords im Output: +{keyword_hit}")
        details.append(f"Output-Qualität: {quality['label']} ({len(output.strip())} Zeichen)")

        # ── Entscheidungslogik ───────────────────────────────────────────────

        # Kritischer Fehler + kein Erfolg + keine Dateien
        if error_score >= 10 and success_score < 5 and not fs_result["found"]:
            confidence = min(97, 65 + error_score * 2)
            return EvalResult(
                status="nachbessern",
                confidence=confidence,
                grund=f"Kritischer Fehler: {error_hits[0][1]}",
                details=details,
                verbesserungs_prompt=self._make_retry_prompt(task, output, error_hits, fs_result)
            )

        # Erwartete Dateien fehlen komplett
        if fs_result["missing"] and not fs_result["found"] and task_info["expected_files"]:
            confidence = 82
            return EvalResult(
                status="nachbessern",
                confidence=confidence,
                grund=f"Erwartete Dateien nicht erstellt: {', '.join(fs_result['missing'])}",
                details=details,
                verbesserungs_prompt=self._make_retry_prompt(task, output, error_hits, fs_result)
            )

        # Eindeutiger Erfolg
        if net >= 8 or (fs_result["found"] and error_score < 5 and success_score >= 5):
            confidence = min(99, 68 + net * 2 + fs_bonus)
            return EvalResult(
                status="gut",
                confidence=confidence,
                grund=f"Aufgabe erfolgreich — {success_hits[0][1] if success_hits else 'Filesystem OK'}",
                details=details
            )

        # Filesystem allein genügt wenn keine Fehler
        if fs_result["found"] and error_score < 8:
            confidence = min(92, 72 + fs_bonus)
            return EvalResult(
                status="gut",
                confidence=confidence,
                grund=f"Dateien korrekt erstellt: {', '.join(fs_result['found'])}",
                details=details
            )

        # Deutlich mehr Fehler als Erfolg
        if net <= -4 or (error_score > success_score + 4 and error_score >= 6):
            confidence = min(92, 58 + abs(net) * 2)
            return EvalResult(
                status="nachbessern",
                confidence=confidence,
                grund=f"Fehlerscore überwiegt (net={net})",
                details=details,
                verbesserungs_prompt=self._make_retry_prompt(task, output, error_hits, fs_result)
            )

        # Claude blockiert / verwirrt
        claude_blocks = [n for _, n, _ in error_hits if n.startswith("claude_")]
        if len(claude_blocks) >= 2:
            return EvalResult(
                status="nachbessern",
                confidence=75,
                grund=f"Claude blockiert: {', '.join(claude_blocks[:2])}",
                details=details,
                verbesserungs_prompt=self._make_retry_prompt(task, output, error_hits, fs_result)
            )

        # Leerer / zu kurzer Output
        if quality["label"] in ("leer", "zu_kurz") and not success_hits:
            return EvalResult(
                status="nachbessern",
                confidence=65,
                grund="Output zu kurz/leer, keine Bestätigung",
                details=details,
                verbesserungs_prompt=f"{task}\n\nBitte erledige die Aufgabe vollständig. Bestätige am Ende welche Dateien erstellt/geändert wurden und liste sie auf."
            )

        # Schwaches positiv-Signal
        if success_hits and error_score < 4:
            return EvalResult(
                status="gut",
                confidence=62,
                grund=f"Schwaches Erfolgs-Signal: {success_hits[0][1]}",
                details=details
            )

        return EvalResult(
            status="gut",
            confidence=52,
            grund="Keine klaren Fehler gefunden (Tendenz: okay)",
            details=details
        )

    # ─── Scanner ─────────────────────────────────────────────────────────────

    def _find_errors(self, output: str) -> list[tuple]:
        hits = []
        for pattern, name, weight in ERROR_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE | re.MULTILINE):
                hits.append((pattern, name, weight))
        return sorted(hits, key=lambda x: -x[2])

    def _find_successes(self, output: str) -> list[tuple]:
        hits = []
        for pattern, name, weight in SUCCESS_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE | re.MULTILINE):
                hits.append((pattern, name, weight))
        return sorted(hits, key=lambda x: -x[2])

    def _check_keyword_coverage(self, task_info: dict, output: str) -> int:
        if not task_info["keywords"]:
            return 0
        lower = output.lower()
        hits = sum(1 for kw in task_info["keywords"] if kw.lower() in lower)
        ratio = hits / len(task_info["keywords"])
        if ratio >= 0.7:
            return 4
        if ratio >= 0.4:
            return 2
        return 0

    # ─── Task-Parsing ─────────────────────────────────────────────────────────

    def _parse_task(self, task: str) -> dict:
        info = {"type": "generic", "expected_files": [], "keywords": [], "raw": task}

        file_matches = re.findall(r'\b[\w\-]+\.\w{1,10}\b', task)
        for m in file_matches:
            ext = os.path.splitext(m)[1].lower()
            if ext in FILE_EXTENSIONS:
                info["expected_files"].append(m)

        for pattern, task_type in TASK_PATTERNS:
            if re.search(pattern, task, re.IGNORECASE):
                info["type"] = task_type
                break

        words = re.findall(r'\b[A-Za-zÄÖÜäöüß_]\w{2,}\b', task)
        info["keywords"] = [w for w in words if w.lower() not in STOPWORDS][:12]

        return info

    # ─── Filesystem-Check ────────────────────────────────────────────────────

    def _check_filesystem(self, task_info: dict, directory: str) -> dict:
        result = {"found": [], "missing": [], "bonus": 0, "penalty": 0}

        if not os.path.isdir(directory):
            return result

        actual_files = set()
        for root, dirs, files in os.walk(directory):
            depth = root.replace(directory, "").count(os.sep)
            if depth > 3:
                continue
            for f in files:
                actual_files.add(f)
                actual_files.add(os.path.relpath(os.path.join(root, f), directory))

        for expected in task_info["expected_files"]:
            basename = os.path.basename(expected)
            if basename in actual_files or expected in actual_files:
                result["found"].append(basename)
                result["bonus"] += 9
                # Bonus wenn Datei nicht leer ist
                for root, _, files in os.walk(directory):
                    for f in files:
                        if f == basename:
                            full = os.path.join(root, f)
                            if os.path.getsize(full) > 10:
                                result["bonus"] += 3
            else:
                result["missing"].append(basename)
                result["penalty"] += 5

        if not task_info["expected_files"] and len(actual_files) > 0:
            result["bonus"] += 2

        return result

    # ─── Output-Qualität ─────────────────────────────────────────────────────

    def _assess_output_quality(self, output: str) -> dict:
        stripped = output.strip()
        length = len(stripped)

        if length == 0:
            return {"score": -6, "label": "leer"}
        if length < 30:
            return {"score": -3, "label": "zu_kurz"}
        if length < 150:
            return {"score": -1, "label": "kurz"}
        if length < 1000:
            return {"score": 2, "label": "normal"}
        if length < 5000:
            return {"score": 4, "label": "ausführlich"}
        if length < 15000:
            return {"score": 3, "label": "sehr_ausführlich"}
        return {"score": 1, "label": "sehr_lang"}

    # ─── Retry-Prompt Generator ──────────────────────────────────────────────

    def _make_retry_prompt(self, task: str, output: str, error_hits: list, fs_result: dict) -> str:
        parts = [task]

        if error_hits:
            top_error = error_hits[0][1]
            advice = ERROR_ADVICE.get(top_error)
            if not advice:
                # Fallback: parent-Kategorie suchen
                for key in ERROR_ADVICE:
                    if key in top_error or top_error.startswith(key.split("_")[0]):
                        advice = ERROR_ADVICE[key]
                        break
            if not advice:
                advice = "Analysiere den Fehler systematisch und behebe die Grundursache."
            parts.append(f"\nHinweis zum Fehler ({top_error}): {advice}")

        if fs_result["missing"]:
            parts.append(f"\nFolgende Dateien MÜSSEN erstellt werden: {', '.join(fs_result['missing'])}")

        if output.strip():
            last_lines = "\n".join(output.strip().splitlines()[-20:])
            parts.append(f"\nLetzter Output:\n```\n{last_lines}\n```")

        parts.append("\nErledige die Aufgabe vollständig und autonom. Bestätige am Ende welche Dateien erstellt/geändert wurden.")
        return "\n".join(parts)


# ─── Öffentliche API ─────────────────────────────────────────────────────────

_evaluator = LocalEvaluator()


def evaluate_output(task: str, output: str, directory: str = "/tmp", api_key: str = "") -> dict:
    return _evaluator.evaluate(task, output, directory).to_dict()


def evaluate_with_report(task: str, output: str, directory: str = "/tmp") -> EvalResult:
    return _evaluator.evaluate(task, output, directory)


# ─── CLI-Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("Erstelle eine hello.py die 'Hello from Jarvis!' ausgibt",
         "Created hello.py successfully.\n\nDone! File written.",
         "/tmp/jarvis-test"),
        ("Erstelle eine app.py mit Flask server",
         "Traceback (most recent call last):\n  File 'app.py', line 3, in <module>\nModuleNotFoundError: No module named 'flask'",
         "/tmp"),
        ("Fix the login bug in auth.js",
         "I'm unable to access the auth.js file. I don't have access to your filesystem. Please provide more context.",
         "/tmp"),
        ("Install numpy and create matrix.py",
         "", "/tmp"),
        ("Build a React component Button.tsx",
         "error TS2345: Argument of type 'string' is not assignable to parameter of type 'number'.\nBuild failed.",
         "/tmp"),
        ("Deploy the app to production",
         "Deploying to Heroku... done\nLive at https://myapp.herokuapp.com\nDeployment complete!",
         "/tmp"),
        ("Run pytest and fix failing tests",
         "FAILED tests/test_api.py::test_login - AssertionError: assert 401 == 200\n2 failed, 8 passed",
         "/tmp"),
        ("Create a PostgreSQL migration for users table",
         "Migration created: 0001_create_users_table.sql\nMigration applied successfully. 1 row affected.",
         "/tmp"),
    ]

    print("=" * 70)
    print("JARVIS LOCAL EVALUATOR — TEST (200+ Muster)")
    print("=" * 70)

    for task, output, directory in tests:
        result = evaluate_with_report(task, output, directory)
        icon = "✅" if result.status == "gut" else "🔁"
        print(f"\n{icon} Task:    {task[:65]}")
        print(f"   Status:  {result.status} (Confidence: {result.confidence}%)")
        print(f"   Grund:   {result.grund}")
        for d in result.details:
            print(f"   · {d}")
        if result.verbesserungs_prompt:
            preview = result.verbesserungs_prompt[:100].replace("\n", " ")
            print(f"   Retry:   {preview}…")
        print("-" * 70)

    print(f"\nMuster geladen: {len(ERROR_PATTERNS)} Fehler · {len(SUCCESS_PATTERNS)} Erfolg · {len(TASK_PATTERNS)} Tasks · {len(FILE_EXTENSIONS)} Dateitypen · {len(ERROR_ADVICE)} Ratschläge")
