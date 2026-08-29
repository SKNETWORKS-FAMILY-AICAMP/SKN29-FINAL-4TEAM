import "./Pagination.css";

interface PaginationProps {
  ariaLabel?: string;
  page: number;
  totalItems: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export default function Pagination({
  ariaLabel = "문의 목록 페이지",
  page,
  totalItems,
  totalPages,
  onPageChange,
}: PaginationProps) {
  const canGoPrevious = page > 1;
  const canGoNext = page < totalPages;

  return (
    <nav className="common-pagination" aria-label={ariaLabel}>
      <p className="common-pagination__summary" aria-live="polite">
        총 {totalItems}건 · {page}/{totalPages}페이지
      </p>

      <div className="common-pagination__actions">
        <button
          type="button"
          disabled={!canGoPrevious}
          onClick={() => onPageChange(page - 1)}
        >
          이전
        </button>

        <span aria-current="page">{page}</span>

        <button
          type="button"
          disabled={!canGoNext}
          onClick={() => onPageChange(page + 1)}
        >
          다음
        </button>
      </div>
    </nav>
  );
}
