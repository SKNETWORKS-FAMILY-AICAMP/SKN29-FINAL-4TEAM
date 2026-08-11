import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import OperationsDashboardPage from "../../pages/admin/OperationsDashboardPage";
import OperationsInfographicPage from "../../pages/admin/OperationsInfographicPage";
import LoginPage from "../../pages/auth/LoginPage";
import ConsultantDashboardPage from "../../pages/consultant/ConsultantDashboardPage";
import InquiryDetailPage from "../../pages/consultant/InquiryDetailPage";
import PhoneInquiryCreatePage from "../../pages/consultant/PhoneInquiryCreatePage";
import VisitTransitionPage from "../../pages/consultant/VisitTransitionPage";
import ErrorPage from "../../pages/system/ErrorPage";
import ForbiddenPage from "../../pages/system/ForbiddenPage";
import NotFoundPage from "../../pages/system/NotFoundPage";
import AdminLayout from "../layouts/AdminLayout";
import AuthLayout from "../layouts/AuthLayout";
import ConsultantLayout from "../layouts/ConsultantLayout";
import RootLayout from "../layouts/RootLayout";
import { useAuth } from "../providers/authContext";
import AuthGuard from "./guards/AuthGuard";
import RoleGuard from "./guards/RoleGuard";
import { ROUTE_PATHS } from "./routePaths";

function HomeRedirect() {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated || !user) {
    return <Navigate to={ROUTE_PATHS.login} replace />;
  }
  if (user.roleCode === "CONSULTANT") {
    return <Navigate to={ROUTE_PATHS.consultantInquiryList} replace />;
  }
  if (user.roleCode === "OPERATOR") {
    return <Navigate to={ROUTE_PATHS.adminDashboard} replace />;
  }
  return <Navigate to={ROUTE_PATHS.forbidden} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<RootLayout />}>
        <Route path={ROUTE_PATHS.home} element={<HomeRedirect />} />

        <Route element={<AuthLayout />}>
          <Route path={ROUTE_PATHS.login} element={<LoginPage />} />
        </Route>

        <Route path={ROUTE_PATHS.forbidden} element={<ForbiddenPage />} />
        <Route path={ROUTE_PATHS.error} element={<ErrorPage />} />

        <Route element={<AuthGuard />}>
          <Route element={<RoleGuard allowedRoles={["CONSULTANT"]} />}>
            <Route element={<ConsultantLayout />}>
              <Route
                path={ROUTE_PATHS.consultantInquiryList}
                element={<ConsultantDashboardPage />}
              />
              <Route
                path={ROUTE_PATHS.consultantPhoneInquiryCreate}
                element={<PhoneInquiryCreatePage />}
              />
              <Route
                path={ROUTE_PATHS.consultantInquiryDetail}
                element={<InquiryDetailPage />}
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
