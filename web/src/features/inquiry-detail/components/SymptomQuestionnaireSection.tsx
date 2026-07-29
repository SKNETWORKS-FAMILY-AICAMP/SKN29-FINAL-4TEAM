import type { InquiryDetailViewModel } from "../model/inquiryDetailTypes";

interface SymptomQuestionnaireSectionProps {
  inquiry: InquiryDetailViewModel;
}

export default function SymptomQuestionnaireSection({
  inquiry,
}: SymptomQuestionnaireSectionProps) {
  return (
    <>
      <section className="inquiry-detail__card">
        <h2>대표 증상</h2>
        <p>{inquiry.symptomSummary}</p>
      </section>

      <section className="inquiry-detail__card">
        <h2>고객 문의 원문</h2>
        <p>{inquiry.customerMessage}</p>
      </section>

      <section className="inquiry-detail__card">
        <h2>문진 및 추가 답변</h2>
        <p>{inquiry.questionnaireAnswer}</p>
      </section>
    </>
  );
}
