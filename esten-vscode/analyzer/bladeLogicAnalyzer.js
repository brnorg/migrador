function analyzeBladeLogicXml(xmlContent, filePath) {
  const lines = xmlContent.split(/\r?\n/);
  const tags = collectXmlTags(xmlContent);
  const uniqueTags = [...new Set(tags)];

  return [
    'BladeLogic XML - Analise',
    `Arquivo: ${filePath}`,
    `Linhas: ${lines.length}`,
    `Caracteres: ${xmlContent.length}`,
    `Tags encontradas: ${tags.length}`,
    `Tags diferentes: ${uniqueTags.length}`,
    `Primeira tag: ${uniqueTags[0] || 'nenhuma'}`,
    '',
    'Tags:',
    uniqueTags.length ? uniqueTags.map((tag) => `- ${tag}`).join('\n') : '- nenhuma tag XML encontrada'
  ].join('\n');
}

function collectXmlTags(xmlContent) {
  const tags = [];
  const tagPattern = /<\s*\/?\s*([a-zA-Z_][\w:.-]*)\b[^>]*>/g;
  let match;

  while ((match = tagPattern.exec(xmlContent)) !== null) {
    const rawTagName = match[1];

    if (rawTagName.startsWith('?') || rawTagName.startsWith('!')) {
      continue;
    }

    tags.push(rawTagName.toLowerCase());
  }

  return tags;
}

module.exports = {
  analyzeBladeLogicXml
};
