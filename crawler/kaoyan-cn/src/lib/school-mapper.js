export function getLabels(school) {
  const labels = [];
  if (school.is_985 === 1) labels.push("985");
  if (school.is_211 === 1) labels.push("211");
  if (school.syl === 1) labels.push("双一流");
  if (school.is_zihuaxian === 1) labels.push("自划线");
  if (school.is_apply === 1) labels.push("申请制");
  if (school.type_school === 2) labels.push("科研院所");
  if (school.is_ordinary === 1) labels.push("普通院校");
  return labels;
}

export function getLinks(school) {
  if (school.is_apply === 1) return ["招生计划", "招生信息"];
  return ["招生简章", "招生计划", "复试分数", "历年真题", "调剂查询"];
}

export function mapSchoolRecord(raw) {
  return {
    id: raw.school_id,
    name: raw.school_name,
    location: raw.province_name,
    area: raw.province_area === "A" ? "A区" : raw.province_area === "B" ? "B区" : "其他",
    type: raw.type_name,
    labels: getLabels(raw),
    links: getLinks(raw),
    logo: `https://static.kaoyan.cn/image/logo/${raw.school_id}_log.jpg`,
  };
}
