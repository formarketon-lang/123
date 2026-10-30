"""TradeLab Pro - RS Engine Compatibility Layer."""

from core.validation import (
    normalize_price_data as _normalize_price_data,
    validate_date_range as _validate_date_range,
)

from core.returns import (
    calculate_return,
    relative_performance,
    calculate_period_return,
    calculate_return_windows,
    calculate_trading_day_return,
)

from core.comparison import (
    compare_on_common_dates,
    compare_stock_with_benchmark,
    compare_stock_with_sector,
    compare_stock_sector_benchmark,
    compare_trading_day_performance,
)
