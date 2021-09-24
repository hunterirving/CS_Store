class Node {
  constructor({x, y, z, w, type, path}) {
    this.type = type;
    this.path = path;

    this.elem = document.createElement("div");
    const content = this.createContent(type, path);
    this.elem.appendChild(content);

    // Depths:
    // 0: scene
    // 1: items in scene
    // 2: stage
    // 3: items in stage
    // 4: item in focus

    // Positioning and rendering
    this.position = new Vec({x, y});
    this.width = w;
    this.depth = z;
    this.inStage = false;
    this.stageWidth = 120;

    // Interaction helpers
    this.dragging = false;
    this.click = null;

    this.elem.addEventListener("mousedown", (e) => this.mousedown(e));
    this.elem.addEventListener('mousemove', (e) => this.mousemove(e));
    this.elem.addEventListener('mouseup', (e) => this.mouseup(e));
  }

  serialize() {
    return {
      x: this.position.x,
      y: this.position.y,
      z: this.depth,
      w: this.width,
      type: this.type,
      path: this.path
    }
  }

  clone() {
    return new this.constructor(this.serialize());
  }

  createContent(type, path) {
    if (type == "image/jpeg") {
      const img = document.createElement("img");
      img.style.width = "100%";
      img.src = path;
      return img;
    }
  }

  render() {
    const pos = scene.toViewport(this.position);
    const w = scene.scale * this.width;
    this.elem.style.left = pos.x;
    this.elem.style.top = pos.y;
    this.elem.style.width = w;
    this.elem.style.zIndex = this.depth;
  }

  getViewportPosition() {
    return new Vec({
      x: parseInt(this.elem.style.left.slice(0, -2)),
      y: parseInt(this.elem.style.top.slice(0, -2)),
    })
  }

  setViewportPosition(v) {
    this.elem.style.left = v.x;
    this.elem.style.top = v.y;
    this.position = scene.toAbsolute(v);
  }

  moveInViewport(delta) {
    const pos = this.getViewportPosition();
    this.setViewportPosition(pos.add(delta));
  }

  mousedown(e) {
    e.preventDefault();
    e.stopPropagation();

    this.dragging = true;
    this.click = new Vec({x: e.clientX, y: e.clientY});

    if (this.inStage) {
      const copy = this.clone();
      copy.depth = 4;

      const rect = this.elem.getBoundingClientRect();
      const pos = new Vec({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      })
      copy.position = scene.toAbsolute(this.click.sub(pos));
      scene.addNode(copy);
      copy.elem.dispatchEvent(new Event('mousedown'));

    } else {
      this.depth = 4;
      this.render();
    }
  }

  mousemove(e) {
    if (this.dragging) {
      const click = new Vec({x: e.clientX, y: e.clientY});
      const delta = click.sub(this.click);
      this.moveInViewport(delta);
      this.click = click;
    }
  }

  mouseup(e) {
    if (this.dragging) {
      this.dragging = false;
      this.render();
      this.depth = 1;
    }
  }
}

class Scene {
  constructor(elem) {
    this.elem = elem;
    this.origin = new Vec({x: 0, y: 0});
    this.scale = 1;
    this.children = [];

    this.elem.addEventListener("wheel", (e) => this.wheel(e))
    this.elem.addEventListener("gesturestart", (e) => e.preventDefault())
    this.elem.addEventListener("gesturechange", (e) => this.gesturechange(e))
    this.elem.addEventListener("gestureend", (e) => e.preventDefault())
    this.elem.addEventListener("mousedown", (e) => e.preventDefault())
    this.elem.addEventListener("mousemove", (e) => e.preventDefault())
    this.elem.addEventListener("mouseup", (e) => e.preventDefault())
  }

  toViewport(x) {
    return x.sub(this.origin).times(this.scale);
  }

  toAbsolute(x) {
    return x.times(1/this.scale).add(this.origin);
  }

  addNode(node) {
    node.elem.classList.add("nodeInScene");
    this.elem.appendChild(node.elem);
    this.children.push(node);
    node.render();
  }

  removeNode(node) {
    node.elem.classList.remove("nodeInScene");
    this.elem.removeChild(node.elem);
    const idx = this.children.indexOf(node);
    this.children.splice(idx, 1);
  }

  render() {
    this.children.map(c => c.render());
  }

  wheel(e) {
    // dev.to/danburzo/pinch-me-i-m-zooming-gestures-in-the-dom-a0e
    e.preventDefault();

    if (e.ctrlKey) {
      // TODO: handle zoom in Chrome

    } else {
      const delta = new Vec({x: -e.deltaX, y: -e.deltaY});
      this.origin = this.origin.add(delta);
      this.render();
    }
  }

  gesturechange(e) {
    e.preventDefault();
    const pointer = new Vec({x: e.clientX, y: e.clientY});
    const a = this.toAbsolute(pointer);

    // Resize the canvas
    const factor = 1 + 0.05 * (e.scale - 1);
    this.scale = clamp(this.scale * factor, 0.3, 3.0);

    // Re-position so mouse remains where it was
    const b = this.toAbsolute(pointer);
    const delta = b.sub(a);
    this.origin = this.origin.sub(delta);
    this.render();
  }
}

class Stage {
  constructor(elem) {
    this.elem = elem;
    this.children = [];
  }

  addNode(node) {
    node.inStage = true;
    node.elem.classList.add("nodeInStage");
    this.elem.appendChild(node.elem);
    this.children.push(node);
  }

  removeNode(node) {
    node.inStage = false;
    node.elem.classList.remove("nodeInStage");
    this.elem.removeChild(node.elem);
    const idx = this.children.indexOf(node);
    this.children.splice(idx, 1);
  }

  inStage(v) {
    const bbox = this.elem.getBoundingClientRect();
    return (
      bbox.left < v.x &&
      v.x < bbox.right &&
      bbox.top < v.y &&
      v.y < bbox.bottom
    );
  }
}
