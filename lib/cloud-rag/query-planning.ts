export type QueryPlan = {
  original: string;
  mode: "simple" | "complex";
  subqueries: string[];
  maxRounds: 1 | 2;
};

const complexMarkers = ["compare", "comparison", "summarize", "summary", "across", "differences", "对比", "比较", "总结", "归纳", "综合", "分别", "哪些项目", "项目和技能"];
const sensitiveMarkers = ["passport", "salary", "gpa", "home address", "date of birth", "birthday", "phone number", "private email", "wechat", "raw file", "full private", "private resume", "护照", "薪资", "工资", "绩点", "住址", "家庭地址", "出生日期", "生日", "手机号码", "电话号码", "私人邮箱", "微信号", "私有文件", "原始文件", "未公开", "简历全文"];

export function shouldRefuseWithoutRetrieval(question: string): boolean {
  const lowered = question.toLowerCase();
  return sensitiveMarkers.some((marker) => lowered.includes(marker));
}

export function planQuery(question: string): QueryPlan {
  const original = question.trim();
  if (!complexMarkers.some((marker) => original.toLowerCase().includes(marker))) {
    return { original, mode: "simple", subqueries: [original], maxRounds: 1 };
  }
  const pieces = original.split(/\b(?:and|versus|vs\.?|compared with)\b|[、，]|(?:和|与)/i).map((part) => part.trim()).filter((part) => part.length >= 4);
  return { original, mode: "complex", subqueries: Array.from(new Set([original, ...pieces])).slice(0, 3), maxRounds: 2 };
}
