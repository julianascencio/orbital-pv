import { useEffect, useRef } from "react";
import {
  ArcType,
  buildModuleUrl,
  CallbackProperty,
  Cartesian2,
  Cartesian3,
  ClockRange,
  ClockStep,
  Color,
  EllipsoidTerrainProvider,
  ImageryLayer,
  JulianDate,
  LabelStyle,
  SampledPositionProperty,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  TileMapServiceImageryProvider,
  Viewer,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import type { MapScene, MapTrack } from "../api";
import { sampleAt, splitGroundTrack } from "../tracking";

type Props = {
  scene?: MapScene;
  selectedId?: string;
  groundTrack?: MapTrack;
  onSelect: (id: string) => void;
};
export function SpaceGlobe({
  scene,
  selectedId,
  groundTrack,
  onSelect,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const modeRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!containerRef.current) return;
    const viewer = new Viewer(containerRef.current, {
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      baseLayer: ImageryLayer.fromProviderAsync(
        TileMapServiceImageryProvider.fromUrl(
          buildModuleUrl("Assets/Textures/NaturalEarthII"),
        ),
      ),
      terrainProvider: new EllipsoidTerrainProvider(),
      geocoder: false,
      homeButton: true,
      sceneModePicker: true,
      navigationHelpButton: false,
      infoBox: false,
      selectionIndicator: false,
      shouldAnimate: true,
    });
    viewer.scene.globe.enableLighting = true;
    viewer.scene.globe.baseColor = Color.fromCssColorString("#102338");
    viewer.scene.backgroundColor = Color.fromCssColorString("#020711");
    const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction((event: { position: Cartesian2 }) => {
      const id: unknown = viewer.scene.pick(event.position)?.id?.id;
      if (typeof id === "string" && !id.startsWith("ground:"))
        onSelectRef.current(id);
    }, ScreenSpaceEventType.LEFT_CLICK);
    viewerRef.current = viewer;
    return () => {
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    for (const entity of [...viewer.entities.values])
      if (!entity.id.startsWith("ground:")) viewer.entities.remove(entity);
    if (!scene?.tracks.length) return;
    scene.tracks.forEach((track) => {
      const position = new SampledPositionProperty();
      for (const sample of track.samples)
        position.addSample(
          JulianDate.fromIso8601(sample.timestamp),
          Cartesian3.fromDegrees(
            sample.longitude_deg,
            sample.latitude_deg,
            sample.altitude_m,
          ),
        );
      viewer.entities.add({
        id: track.satellite_id,
        name: track.name,
        position,
        point: {
          pixelSize: track.satellite_id === selectedId ? 12 : 7,
          color: new CallbackProperty((time) => {
            if (!time) return Color.GRAY;
            const fraction = sampleAt(
              track.samples,
              JulianDate.toDate(time).getTime(),
            )?.illumination_fraction;
            return fraction == null
              ? Color.GRAY
              : fraction <= 0.001
                ? Color.ORANGE
                : Color.CYAN;
          }, false),
          outlineColor: Color.WHITE,
          outlineWidth: track.satellite_id === selectedId ? 2 : 0,
        },
        label: {
          show: track.satellite_id === selectedId,
          text: track.name,
          font: "13px sans-serif",
          fillColor: Color.WHITE,
          outlineColor: Color.BLACK,
          outlineWidth: 3,
          style: LabelStyle.FILL_AND_OUTLINE,
          pixelOffset: new Cartesian2(14, -16),
        },
      });
    });
    if (scene.mode === "live") {
      viewer.clock.clockRange = ClockRange.UNBOUNDED;
      viewer.clock.clockStep = ClockStep.SYSTEM_CLOCK;
      viewer.clock.multiplier = 1;
      viewer.clock.currentTime = JulianDate.now();
    } else if (modeRef.current !== "demo") {
      const samples = scene.tracks[0].samples;
      viewer.clock.startTime = JulianDate.fromIso8601(samples[0].timestamp);
      viewer.clock.stopTime = JulianDate.fromIso8601(
        samples[samples.length - 1].timestamp,
      );
      viewer.clock.currentTime = viewer.clock.startTime.clone();
      viewer.clock.clockStep = ClockStep.SYSTEM_CLOCK_MULTIPLIER;
      viewer.clock.clockRange = ClockRange.LOOP_STOP;
      viewer.clock.multiplier = 120;
    }
    viewer.clock.shouldAnimate = true;
    modeRef.current = scene.mode;
  }, [scene, selectedId]);
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    for (const entity of [...viewer.entities.values])
      if (entity.id.startsWith("ground:")) viewer.entities.remove(entity);
    if (!groundTrack) return;
    splitGroundTrack(groundTrack.samples).forEach((part, index) =>
      viewer.entities.add({
        id: `ground:${index}`,
        polyline: {
          positions: part.map((s) =>
            Cartesian3.fromDegrees(s.longitude_deg, s.latitude_deg, 1000),
          ),
          arcType: ArcType.GEODESIC,
          width: 2,
          material: Color.fromCssColorString("#a6ceff").withAlpha(0.7),
        },
      }),
    );
  }, [groundTrack]);
  return (
    <div
      className="space-globe"
      ref={containerRef}
      aria-label="Interactive satellite globe"
    />
  );
}
