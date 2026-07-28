import { useState } from "react";

interface InquiryResponseFormState {
  inquiryId?: string;
  value: string;
}

export default function useInquiryResponseForm(
  inquiryId: string | undefined,
  initialResponseDraft: string,
) {
  const [responseDraftState, setResponseDraftState] = useState<
    InquiryResponseFormState
  >(() => ({ inquiryId, value: initialResponseDraft }));
  const [actionMessageState, setActionMessageState] = useState<
    InquiryResponseFormState
  >(() => ({ inquiryId, value: "" }));

  const responseDraft =
    responseDraftState.inquiryId === inquiryId
      ? responseDraftState.value
      : initialResponseDraft;
  const actionMessage =
    actionMessageState.inquiryId === inquiryId
      ? actionMessageState.value
      : "";

  return {
    actionMessage,
    responseDraft,
    setActionMessage: (value: string) =>
      setActionMessageState({ inquiryId, value }),
    setResponseDraft: (value: string) =>
      setResponseDraftState({ inquiryId, value }),
  };
}
