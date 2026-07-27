import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import ConsultantDashboardPage from "../../pages/consultant/ConsultantDashboardPage";
import InquiryDetailPage from "../../pages/consultant/InquiryDetailPage";
import { ROUTE_PATHS } from "./routePaths";

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path={ROUTE_PATHS.home}
          element={
            <Navigate
              to={ROUTE_PATHS.consultantInquiryList}
              replace
            />
          }
        />

        <Route
          path={ROUTE_PATHS.consultantInquiryList}
          element={<ConsultantDashboardPage />}
        />

        <Route
          path={ROUTE_PATHS.consultantInquiryDetail}
          element={<InquiryDetailPage />}
        />

        <Route
          path="*"
          element={
            <main style={{ padding: "32px" }}>
              <h1>페이지를 찾을 수 없습니다.</h1>
            </main>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
