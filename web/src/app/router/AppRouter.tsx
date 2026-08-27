import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useParams,
} from "react-router-dom";

import OperationsDashboardPage from "../../pages/admin/OperationsDashboardPage";
import OperationsInfographicPage from "../../pages/admin/OperationsInfographicPage";
import LoginPage from "../../pages/auth/LoginPage";
import ConsultantDashboardPage from "../../pages/consultant/ConsultantDashboardPage";
import ConsultantInquiryListPage from "../../pages/consultant/ConsultantInquiryListPage";
import ConsultantNoticePage from "../../pages/consultant/ConsultantNoticePage";
import PhoneInquiryCreatePage from "../../pages/consultant/PhoneInquiryCreatePage";
import VisitTransitionPage from "../../pages/consultant/VisitTransitionPage";
import LandingPage from "../../pages/landing/LandingPage";
import ErrorPage from "../../pages/system/ErrorPage";
import ForbiddenPage from "../../pages/system/ForbiddenPage";
import NotFoundPage from "../../pages/system/NotFoundPage";
import LoadingState from "../../common/components/feedback/LoadingState";
import AdminLayout from "../layouts/AdminLayout";
import AuthLayout from "../layouts/AuthLayout";
import ConsultantLayout from "../layouts/ConsultantLayout";
import RootLayout from "../layouts/RootLayout";
import { useAuth } from "../providers/authContext";
import { toInquiryId } from "../../entities/inquiry/inquiryIdentifiers";
import AuthGuard from "./guards/AuthGuard";
import RoleGuard from "./guards/RoleGuard";
import { createInquiryDetailPath, ROUTE_PATHS } from "./routePaths";

function HomeRoute() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return <LoadingState title="로그인 상태를 확인하고 있습니다." />;
  }

  if (!isAuthenticated || !user) {
    return <LandingPage />;
  }
  if (user.roleCode === "CONSULTANT") {
    return <Navigate to={ROUTE_PATHS.consultantDashboard} replace />;
  }
  if (user.roleCode === "OPERATOR") {
    return <Navigate to={ROUTE_PATHS.adminDashboard} replace />;
  }
  return <Navigate to={ROUTE_PATHS.forbidden} replace />;
}

function LegacyInquiryDetailRedirect() {
  const { inquiryId: rawInquiryId } = useParams<{ inquiryId: string }>();
  const inquiryId = toInquiryId(rawInquiryId);

  return (
    <Navigate
      to={
        inquiryId
          ? createInquiryDetailPath(inquiryId)
          : ROUTE_PATHS.consultantInquiryList
      }
      replace
    />
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<RootLayout />}>
        <Route path={ROUTE_PATHS.home} element={<HomeRoute />} />

        <Route element={<AuthLayout />}>
          <Route path={ROUTE_PATHS.login} element={<LoginPage />} />
        </Route>

        <Route path={ROUTE_PATHS.forbidden} element={<ForbiddenPage />} />
        <Route path={ROUTE_PATHS.error} element={<ErrorPage />} />

        <Route element={<AuthGuard />}>
          <Route element={<RoleGuard allowedRoles={["CONSULTANT"]} />}>
            <Route element={<ConsultantLayout />}>
              <Route
                path={ROUTE_PATHS.consultantDashboard}
                element={<ConsultantDashboardPage />}
              />
              <Route
                path={ROUTE_PATHS.consultantNotices}
                element={<ConsultantNoticePage />}
              />
              <Route
                path={ROUTE_PATHS.consultantInquiryList}
                element={<ConsultantInquiryListPage />}
              />
              <Route
                path={ROUTE_PATHS.consultantPhoneInquiryCreate}
                element={<PhoneInquiryCreatePage />}
              />
              <Route
                path={ROUTE_PATHS.consultantInquiryDetail}
                element={<LegacyInquiryDetailRedirect />}
              />
              <Route
                path={ROUTE_PATHS.consultantVisitTransition}
                element={<VisitTransitionPage />}
              />
            </Route>
          </Route>

          <Route element={<RoleGuard allowedRoles={["OPERATOR"]} />}>
            <Route element={<AdminLayout />}>
              <Route
                path={ROUTE_PATHS.adminDashboard}
                element={<OperationsDashboardPage />}
              />
              <Route
                path={ROUTE_PATHS.adminInsights}
                element={<OperationsInfographicPage />}
              />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default function AppRouter() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
