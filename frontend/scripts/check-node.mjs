const major = Number.parseInt(process.versions.node.split('.')[0], 10)
if (major < 18) {
  console.error(
    `\nNode.js ${process.version} es demasiado antiguo para Vite 5 (hace falta >= 18).\n` +
      `  which node → ${process.execPath}\n\n` +
      'Opciones en este servidor:\n' +
      '  conda install -c conda-forge nodejs=20\n' +
      '  nvm install 20 && nvm use 20\n' +
      '  module load node/20   (si tu cluster lo ofrece)\n',
  )
  process.exit(1)
}
