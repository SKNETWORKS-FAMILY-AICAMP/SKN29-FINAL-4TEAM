import { useState } from "react";

import type { CounselorActionCode } from "../model/consultantWorkspaceTypes";
import type {
  ConsultationField,
  ConsultationFieldErrors,
  ConsultationFormValues,
} from "../model/consultationTypes";
import {
  validateConsultation,
  type ConsultationValidationOptions,
} from "../validation/consultationSchema";

export function useConsultationForm(
  initialValues: ConsultationFormValues,
  validationOptions: ConsultationValidationOptions = {},
) {
  const [values, setValues] = useState(initialValues);
  const [fieldErrors, setFieldErrors] = useState<ConsultationFieldErrors>({});

  const updateField = <Field extends ConsultationField>(
    field: Field,
    value: ConsultationFormValues[Field],
  ) => {
    setValues((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => {
      if (!(field in current)) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
  };

  const validate = (actionCode: CounselorActionCode) => {
    const nextErrors = validateConsultation(
      values,
      actionCode,
      validationOptions,
    );
    setFieldErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  return {
    values,
    fieldErrors,
    updateField,
    validate,
    setServerFieldErrors: setFieldErrors,
  };
}

