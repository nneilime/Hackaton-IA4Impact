/* Petit rendu Markdown local. Chaque texte est inséré avec textContent :
   le HTML du modèle et les images ne sont jamais interprétés. */
(() => {
  function appendText(parent, text) {
    const node = document.createElement('span');
    node.textContent = text;
    parent.append(node);
  }

  function safeLink(value) {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && !url.username && !url.password ? url.href : null;
    } catch { return null; }
  }

  function appendInline(parent, text, depth = 0) {
    if (depth > 3) { appendText(parent, text); return; }
    const tokens = /`([^`\n]+)`|\*\*([^\n]+?)\*\*|__([^\n]+?)__|\*([^*\n]+)\*|_([^_\n]+)_|\[([^\]\n]+)\]\(([^\s)]+)\)/g;
    let position = 0;
    for (const match of text.matchAll(tokens)) {
      appendText(parent, text.slice(position, match.index));
      const [raw, code, bold, boldUnderscore, italic, italicUnderscore, title, address] = match;
      if (title !== undefined) {
        const href = text[match.index - 1] === '!' ? null : safeLink(address);
        if (href) {
          const link = document.createElement('a');
          link.href = href;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          appendInline(link, title, depth + 1);
          parent.append(link);
        } else appendText(parent, raw);
      } else {
        const node = document.createElement(code !== undefined ? 'code' : bold !== undefined || boldUnderscore !== undefined ? 'strong' : 'em');
        const content = code ?? bold ?? boldUnderscore ?? italic ?? italicUnderscore;
        if (code !== undefined) node.textContent = content;
        else appendInline(node, content, depth + 1);
        parent.append(node);
      }
      position = match.index + raw.length;
    }
    appendText(parent, text.slice(position));
  }

  function render(parent, text) {
    parent.className = 'message-markdown';
    let paragraph = null;
    let list = null;
    let listItem = null;
    let fencedCode = null;
    const reset = () => { paragraph = null; list = null; listItem = null; };
    for (const line of text.replace(/\r\n?/g, '\n').split('\n')) {
      if (/^\s*```/.test(line)) {
        reset();
        if (fencedCode) fencedCode = null;
        else {
          const pre = document.createElement('pre');
          fencedCode = document.createElement('code');
          pre.append(fencedCode);
          parent.append(pre);
        }
        continue;
      }
      if (fencedCode) { fencedCode.textContent += line + '\n'; continue; }
      if (!line.trim()) { reset(); continue; }
      const heading = line.match(/^\s{0,3}#{1,6}\s+(.+)$/);
      if (heading) {
        reset();
        const node = document.createElement('h3');
        appendInline(node, heading[1]);
        parent.append(node);
        continue;
      }
      const bullet = line.match(/^\s*(?:([-+*])|(\d+)[.)])\s+(.+)$/);
      if (bullet) {
        paragraph = null;
        const type = bullet[2] ? 'OL' : 'UL';
        if (!list || list.tagName !== type) {
          list = document.createElement(type.toLowerCase());
          if (bullet[2]) list.start = Number(bullet[2]);
          parent.append(list);
        }
        listItem = document.createElement('li');
        appendInline(listItem, bullet[3]);
        list.append(listItem);
        continue;
      }
      if (listItem) {
        appendText(listItem, ' ');
        appendInline(listItem, line.trim());
        continue;
      }
      if (!paragraph) { paragraph = document.createElement('p'); parent.append(paragraph); }
      else paragraph.append(document.createElement('br'));
      appendInline(paragraph, line);
    }
  }
  globalThis.CEMarkdown = {render};
})();
