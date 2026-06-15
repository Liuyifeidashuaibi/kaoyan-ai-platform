import { redirect } from "next/navigation";

/** 院校列表已整合到 /choose-school，详情页仍使用 /schools/[id] */
export default function SchoolsPage() {
  redirect("/choose-school");
}
