// Visionneuse 3D d'un bâtiment : charge un .glb (compressé meshopt), le centre et le met à l'échelle, puis le fait
// tourner lentement jusqu'à ce qu'on le prenne au doigt ou à la souris. Chargée à la demande (React.lazy) pour que
// les loaders three.js ne pèsent pas sur la page tant que personne n'ouvre la 3D.
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { useI18n } from "../i18n";

export default function ModelViewer({ src, label }: { src: string; label: string }) {
  const { t } = useI18n();
  const host = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const el = host.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(3, 5, 2);
    scene.add(sun);

    const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 100);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.autoRotate = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    controls.autoRotateSpeed = 1.2;
    controls.enablePan = false;
    controls.addEventListener("start", () => (controls.autoRotate = false));

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = el;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    resize();

    let disposed = false;
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    loader.load(
      src,
      (gltf) => {
        if (disposed) return;
        const model = gltf.scene;
        // Scan sans texture (Carcassonne) : blanc sur fond blanc, on lui donne une teinte de pierre
        model.traverse((o) => {
          const mesh = o as THREE.Mesh;
          if (!mesh.isMesh || mesh.geometry.attributes.color) return;
          for (const m of [mesh.material].flat() as THREE.MeshStandardMaterial[]) if (!m.map) m.color.set(0xc9b48f);
        });
        // Ramène le modèle à une taille de 2 unités, posé au sol et centré : chaque scan arrive à sa propre échelle
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const scale = 2 / Math.max(size.x, size.y, size.z);
        const center = box.getCenter(new THREE.Vector3());
        model.position.set(-center.x * scale, -box.min.y * scale, -center.z * scale);
        model.scale.setScalar(scale);
        scene.add(model);
        const height = size.y * scale;
        controls.target.set(0, height / 2, 0);
        // Caméra au plus près qui garde les huit coins du bâtiment dans le cadre : à distance fixe, chaque scan
        // paraissait petit (et le viaduc, tout en longueur, minuscule)
        const dir = new THREE.Vector3(1, 0.6, 1).normalize();
        const right = new THREE.Vector3(0, 1, 0).cross(dir).normalize();
        const up = dir.clone().cross(right);
        const tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) * 0.9; // 10 % de marge
        const tanH = tanV * camera.aspect;
        const half = size.clone().multiplyScalar(scale / 2);
        let dist = 0;
        for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) {
          const p = new THREE.Vector3(sx * half.x, sy * half.y, sz * half.z); // relatif au centre visé
          const z = p.dot(dir);
          dist = Math.max(dist, z + Math.abs(p.dot(right)) / tanH, z + Math.abs(p.dot(up)) / tanV);
        }
        camera.position.copy(dir.multiplyScalar(dist)).add(controls.target);
        controls.minDistance = 0.6;
        controls.maxDistance = 6;
        controls.maxPolarAngle = Math.PI / 2 - 0.05; // jamais sous le sol
        setState("ready");
      },
      (e) => e.total && setProgress(e.loaded / e.total),
      () => !disposed && setState("error"),
    );

    renderer.setAnimationLoop(() => {
      controls.update();
      renderer.render(scene, camera);
    });

    return () => {
      disposed = true;
      renderer.setAnimationLoop(null);
      observer.disconnect();
      controls.dispose();
      scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (!mesh.isMesh) return;
        mesh.geometry.dispose();
        for (const m of [mesh.material].flat()) {
          for (const v of Object.values(m)) if (v instanceof THREE.Texture) v.dispose();
          m.dispose();
        }
      });
      scene.environment?.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [src]);

  return (
    <div className="model-viewer" ref={host} role="img" aria-label={label}>
      {state === "loading" && (
        <div className="model-status">
          {t.model3dLoading}
          <span className="model-bar"><span style={{ width: `${Math.round(progress * 100)}%` }} /></span>
        </div>
      )}
      {state === "error" && <div className="model-status">{t.model3dError}</div>}
      {state === "ready" && <div className="model-hint">{t.model3dHint}</div>}
    </div>
  );
}
