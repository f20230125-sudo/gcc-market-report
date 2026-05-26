import { Report } from "@/components/Report";
import { loadReport } from "@/lib/load";

export default function Page() {
  return <Report r={loadReport()} repoUrl={process.env.NEXT_PUBLIC_REPO_URL} />;
}
