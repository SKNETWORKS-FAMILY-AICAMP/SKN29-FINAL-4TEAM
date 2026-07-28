import type { InquiryDetailViewModel } from "../model/inquiryDetailTypes";

interface CustomerProductSectionProps {
  inquiry: InquiryDetailViewModel;
}

export default function CustomerProductSection({
  inquiry,
}: CustomerProductSectionProps) {
  return (
    <div className="inquiry-detail__grid">
      <section className="inquiry-detail__card">
        <h2>고객 정보</h2>

        <dl className="inquiry-detail__data-list">
          <div>
            <dt>고객 표시명</dt>
            <dd>{inquiry.customerDisplayName}</dd>
          </div>

          <div>
            <dt>연락처</dt>
            <dd>{inquiry.maskedPhone}</dd>
          </div>
        </dl>
      </section>

      <section className="inquiry-detail__card">
        <h2>제품 정보</h2>

        <dl className="inquiry-detail__data-list">
          <div>
            <dt>제품 모델</dt>
            <dd>{inquiry.productModel}</dd>
          </div>

          <div>
            <dt>구독 유형</dt>
            <dd>{inquiry.subscriptionType}</dd>
          </div>

          <div>
            <dt>관리 유형</dt>
            <dd>{inquiry.careType}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
