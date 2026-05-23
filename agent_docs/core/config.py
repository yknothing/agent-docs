"""Shared pipeline configuration and constants."""

UA = "Mozilla/5.0 (compatible; AnthropicContentPipeline/1.0)"
DEFAULT_BATCH_SIZE = 20
DEFAULT_TRANSLATE_TIMEOUT = 120
DEFAULT_OUTPUT_ROOT = "artifacts/anthropic-content"
DEFAULT_IMAGE_FETCH_TIMEOUT = 180
DEFAULT_HTTP_TIMEOUT = 30
DEFAULT_SOURCE_PROBE_TIMEOUT = 8
DEFAULT_SYNC_TIMEOUT = 300
AGENT_DOCS_ROOT = "agent-docs"
DEFAULT_VENDOR = "anthropic"

FEISHU_FOLDER_CACHE_NAME = ".feishu_folder_cache.json"
FEISHU_INDEX_DOC_TITLE = "📋 目录总纲"
FEISHU_INDEX_CACHE_NAME = ".feishu_index_cache.json"
FEISHU_FOLDER_INDEX_NAME = "feishu_folder_index.json"
FEISHU_VERIFY_MIN_CONTENT_LEN = 200
FEISHU_DOC_LOCALE_PREFIXES = {"en", "zh-cn", "zh", "zh-hans", "ja", "ko", "fr", "de", "es", "pt", "it"}
FEISHU_EXCLUDED_URL_PATHS = ("/resources/courses",)
FEISHU_MEDIA_CAPTION_MAX_LEN = 200
FEISHU_FOLDER_TOKEN_HASH_LEN = 8
FEISHU_ALT_TEXT_MIN_LEN = 8
FEISHU_ALT_TEXT_HINT_MAX_LEN = 24
FEISHU_ERROR_SNIPPET_MAX_LEN = 300

LOG_SECRET_KEY_FRAGMENTS = ("token", "secret", "password", "api_key", "authorization", "credential")

ALLOWED_SITEMAP_PREFIXES = {
    "news",
    "research",
    "engineering",
    "learn",
    "economic-futures",
    "system-cards",
}

PLATFORM_DOCS_URL = "https://platform.claude.com/llms.txt"
CODE_DOCS_URL = "https://code.claude.com/docs/llms.txt"
SITEMAP_URL = "https://www.anthropic.com/sitemap.xml"

IMAGE_EXTS = {
    ".avif",
    ".bmp",
    ".gif",
    ".jpg",
    ".jpeg",
    ".png",
    ".svg",
    ".webp",
}
DEFAULT_IMAGE_EXT = ".bin"
IMAGE_HASH_HEX_LEN = 12

ALLOWED_DOC_HOSTS = {
    "platform.claude.com",
    "code.claude.com",
}

NEWS_HOSTS = {
    "www.anthropic.com",
    "anthropic.com",
}

# HTTP fetch / retry
HTTP_FETCH_MAX_ATTEMPTS = 3
HTTP_FETCH_RETRY_BASE_SLEEP_SEC = 1
HTTP_FETCH_LAST_ATTEMPT_INDEX = HTTP_FETCH_MAX_ATTEMPTS - 1
HTTP_SUCCESS_STATUS = 200
HTTP_SUCCESS_STATUS_MIN = 200
HTTP_SUCCESS_STATUS_MAX = 299
HTTP_CLIENT_ERROR_MIN = 400
HTTP_CLIENT_ERROR_MAX = 499
HTTP_REDIRECT_CODES = (301, 302, 303, 307, 308)
HTTP_HEAD_UNSUPPORTED_CODES = frozenset({405, 501})
DEFAULT_CHARSET = "utf-8"

# Slug / item directory naming
DEFAULT_SLUG_MAX_LEN = 120
SLUG_HASH_SUFFIX_LEN = 8
ITEM_DIR_INDEX_WIDTH = 3

# Language / content thresholds
CHINESE_RATIO_THRESHOLD = 0.005
MIN_VISIBLE_CONTENT_LEN = 20
TITLE_SCAN_MAX_LINES = 40
HTML_NEWLINE_COLLAPSE_MIN = 3

# OpenAI translation defaults
OPENAI_DEFAULT_API_BASE = "https://api.openai.com/v1/chat/completions"
OPENAI_DEFAULT_CHAT_MODEL = "gpt-4o"
OPENAI_TRANSLATE_TEMPERATURE = 0.1
TRANSLATE_PRESERVED_TERMS = "Agent, Skill, Token, MCP, CLI, API, OAuth, JSON, Markdown, YAML, SDK"

# QA reporting
QA_LOG_MAX_ERRORS = 50
QA_STATUS_PASS = "PASS"
QA_STATUS_FAIL = "FAIL"
QA_STATUS_SKIPPED = "SKIPPED"

# QA error codes — technical
QA_ERR_NOT_FETCHED = "not_fetched"
QA_ERR_EMPTY_OR_TOO_SHORT = "empty_or_too_short_output"
QA_ERR_NOT_FOUND_OUTPUT = "not_found_output"
QA_ERR_BAD_IMAGE_COUNT_SOURCE = "bad_image_count_source"
QA_ERR_BAD_TABLE_COUNT_SOURCE = "bad_table_count_source"
QA_ERR_IMAGE_COUNT_DECREASE = "image_count_decrease"
QA_ERR_TABLE_COUNT_DECREASE = "table_count_decrease"
QA_ERR_HEADING_COUNT_DECREASE = "heading_count_decrease"
QA_ERR_LINK_COUNT_DECREASE = "link_count_decrease"
QA_ERR_IMAGE_DOWNLOAD_FAILED = "image_download_failed"
QA_ERR_IMAGE_FILE_MISSING = "image_file_missing"
QA_ERR_IMAGE_NOT_LOCALIZED = "image_not_localized"

# QA error codes — content
QA_ERR_TRANSLATE_MISSING = "translate_missing"
QA_ERR_ZH_LANGUAGE_CHECK = "zh_output_language_check_failed"

# Crawl / image status strings
CRAWL_STATUS_FETCHED = "fetched"
CRAWL_STATUS_FAILED_FETCH = "failed-fetch"
CRAWL_STATUS_FAILED_EMPTY = "failed-empty-or-not-found"
IMAGE_STATUS_OK = "ok"
IMAGE_STATUS_SKIP = "skip-unsupported"
IMAGE_STATUS_FAILED = "failed-fetch"
FETCH_RETRY_COUNT_LOG = HTTP_FETCH_LAST_ATTEMPT_INDEX
