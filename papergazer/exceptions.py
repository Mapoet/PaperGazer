"""
自定义异常类
"""


class PaperGazerError(Exception):
    """PaperGazer 基础异常"""

    pass


class ConfigurationError(PaperGazerError):
    """配置错误"""

    pass


class DataSourceError(PaperGazerError):
    """数据源错误"""

    pass


class ArxivAPIError(DataSourceError):
    """arXiv API 错误"""

    pass


class CrossrefAPIError(DataSourceError):
    """Crossref API 错误"""

    pass


class UnpaywallAPIError(DataSourceError):
    """Unpaywall API 错误"""

    pass


class EuropePMCAPIError(DataSourceError):
    """Europe PMC API 错误"""

    pass


class StorageError(PaperGazerError):
    """存储错误"""

    pass


class DatabaseError(StorageError):
    """数据库错误"""

    pass


class FileStorageError(StorageError):
    """文件存储错误"""

    pass


class FetchError(PaperGazerError):
    """抓取错误"""

    pass


class ValidationError(PaperGazerError):
    """数据验证错误"""

    pass

